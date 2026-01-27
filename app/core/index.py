import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Union

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import Language, RecursiveCharacterTextSplitter
from langchain.schema import Document

from app.config import settings

logger = logging.getLogger(__name__)


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={'device': 'cpu', 'trust_remote_code': True},
        encode_kwargs={'normalize_embeddings': True},
    )


class CodebaseIndexer:

    INDEXABLE_EXTENSIONS = {
        ".kt": ("kotlin", "kotlin"),
        ".kts": ("kotlin", "kotlin"),
        ".java": ("java", "java"),
        ".gradle": ("gradle", "groovy"),
        ".md": ("markdown", "markdown"),
        ".xml": ("xml", "xml"),
    }

    SKIP_DIRS = {
        ".git",
        ".gradle",
        ".idea",
        "build",
        ".cxx",
        ".kotlin",
    }

    SKIP_PATTERNS = {
        ".so",
        ".jar",
        ".apk",
        ".aar",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".iml",
        ".class",
        ".dex",
    }

    COLLECTION_NAME = settings.collection_name

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embeddings = get_embeddings()
        self._init_splitters()

    def _init_splitters(self) -> None:
        self.kotlin_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.KOTLIN,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        self.markdown_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.MARKDOWN,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        self.java_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.JAVA,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        self.generic_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    def _get_splitter(self, file_type: str) -> RecursiveCharacterTextSplitter:
        if file_type == "kotlin":
            return self.kotlin_splitter
        elif file_type == "markdown":
            return self.markdown_splitter
        elif file_type == "java":
            return self.java_splitter
        else:
            return self.generic_splitter

    def _should_skip_path(self, path: Path) -> bool:
        for part in path.parts:
            if part in self.SKIP_DIRS:
                return True

        if path.suffix.lower() in self.SKIP_PATTERNS:
            return True

        return False

    def _extract_module_name(self, file_path: Path, codebase_root: Path) -> str:
        try:
            relative_path = file_path.relative_to(codebase_root)
            parts = relative_path.parts

            if len(parts) >= 2:
                if parts[0] in ("core", "feature", "third", "build-logic"):
                    return f"{parts[0]}:{parts[1]}"
                elif parts[0] == "app":
                    return "app"
                elif parts[0] == "buildSrc":
                    return "buildSrc"

            return parts[0] if parts else "root"
        except ValueError:
            return "unknown"

    def _iter_files(self, codebase_path: Path) -> Iterator[Path]:
        for file_path in codebase_path.rglob("*"):
            if not file_path.is_file():
                continue
            if self._should_skip_path(file_path):
                continue
            if file_path.suffix.lower() in self.INDEXABLE_EXTENSIONS:
                yield file_path

    def _read_file_safe(self, file_path: Path) -> Optional[str]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            print(f"[SKIP] Failed to read {file_path}: {e}")
            logger.warning(f"Failed to read {file_path}: {e}")
            return None

    def _chunk_file(
        self,
        content: str,
        file_path: Path,
        codebase_root: Path,
    ) -> List[Document]:
        suffix = file_path.suffix.lower()
        file_type, language = self.INDEXABLE_EXTENSIONS.get(
            suffix, ("unknown", "unknown")
        )

        try:
            relative_path = str(file_path.relative_to(codebase_root))
        except ValueError:
            relative_path = str(file_path)

        module_name = self._extract_module_name(file_path, codebase_root)
        splitter = self._get_splitter(file_type)
        chunks = splitter.split_text(content)

        documents = []
        for idx, chunk in enumerate(chunks):
            metadata = {
                "file_path": relative_path,
                "module_name": module_name,
                "file_type": file_type,
                "language": language,
                "chunk_index": idx,
            }
            documents.append(Document(page_content=chunk, metadata=metadata))

        return documents

    def _init_vectorstore(self, reset: bool = False) -> Chroma:
        persist_dir = str(settings.chroma_db_path)

        if reset:
            import shutil

            chroma_path = Path(persist_dir)
            if chroma_path.exists():
                logger.info(f"Resetting vector store at {persist_dir}")
                shutil.rmtree(chroma_path)

        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        return Chroma(
            collection_name=self.COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=persist_dir,
        )

    def index_codebase(
        self,
        codebase_path: Union[str, Path],
        reset: bool = False,
        batch_size: int = 100,
    ) -> Dict:
        codebase_path = Path(codebase_path)
        if not codebase_path.exists():
            raise ValueError(f"Codebase path does not exist: {codebase_path}")

        logger.info(f"Starting indexing of {codebase_path}")
        print(f"[START] Indexing codebase: {codebase_path}")

        vectorstore = self._init_vectorstore(reset=reset)

        all_documents: List[Document] = []
        files_processed = 0
        files_skipped = 0

        for file_path in self._iter_files(codebase_path):
            content = self._read_file_safe(file_path)
            if content is None:
                files_skipped += 1
                continue

            if not content.strip():
                files_skipped += 1
                continue

            chunks = self._chunk_file(content, file_path, codebase_path)
            all_documents.extend(chunks)
            files_processed += 1

            if files_processed % 50 == 0:
                print(
                    f"[PROGRESS] Processed {files_processed} files, "
                    f"{len(all_documents)} chunks"
                )
                logger.info(
                    f"Processed {files_processed} files, "
                    f"{len(all_documents)} chunks so far"
                )

        print(
            f"[COMPLETE] Read {files_processed} files, "
            f"{len(all_documents)} chunks total"
        )
        logger.info(
            f"Finished reading: {files_processed} files, "
            f"{len(all_documents)} chunks total"
        )

        if all_documents:
            print("[EMBEDDING] Adding documents to vector store...")
            logger.info("Adding documents to vector store...")
            for i in range(0, len(all_documents), batch_size):
                batch = all_documents[i : i + batch_size]
                vectorstore.add_documents(batch)
                batch_num = i // batch_size + 1
                total_batches = (len(all_documents) + batch_size - 1) // batch_size
                print(f"[BATCH] Added batch {batch_num}/{total_batches}")
                logger.info(f"Added batch {batch_num}/{total_batches}")

        stats = {
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "chunks_created": len(all_documents),
            "collection_name": self.COLLECTION_NAME,
            "persist_directory": str(settings.chroma_db_path),
        }

        print(f"[DONE] Indexing complete: {stats}")
        logger.info(f"Indexing complete: {stats}")
        return stats
