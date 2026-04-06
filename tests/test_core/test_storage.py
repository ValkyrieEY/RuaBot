"""
Tests for Storage component.

This test suite covers:
- Storage initialization
- File operations
- Directory operations
- Path management
- Error handling
"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from src.core.storage import Storage, init_storage


class TestStorage:
    """Test suite for Storage functionality."""

    @pytest.fixture
    def temp_storage_dir(self) -> Path:
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    async def storage(self, temp_storage_dir: Path) -> Storage:
        """Create a storage instance."""
        storage = await init_storage(str(temp_storage_dir))
        yield storage
        await storage.close()

    @pytest.mark.asyncio
    async def test_storage_initialization(self, temp_storage_dir: Path):
        """Test that storage initializes correctly."""
        storage = await init_storage(str(temp_storage_dir))

        assert storage is not None
        assert storage.base_path == temp_storage_dir
        assert storage.base_path.exists()

        await storage.close()

    @pytest.mark.asyncio
    async def test_storage_create_directory(self, storage: Storage):
        """Test creating a directory."""
        dir_path = storage.base_path / "test_dir"

        await storage.create_directory("test_dir")

        assert dir_path.exists()
        assert dir_path.is_dir()

    @pytest.mark.asyncio
    async def test_storage_create_nested_directory(self, storage: Storage):
        """Test creating nested directories."""
        dir_path = storage.base_path / "parent" / "child" / "grandchild"

        await storage.create_directory("parent/child/grandchild")

        assert dir_path.exists()
        assert dir_path.is_dir()

    @pytest.mark.asyncio
    async def test_storage_write_file(self, storage: Storage):
        """Test writing a file."""
        file_path = storage.base_path / "test.txt"
        content = "Hello, World!"

        await storage.write_file("test.txt", content)

        assert file_path.exists()
        assert file_path.read_text() == content

    @pytest.mark.asyncio
    async def test_storage_read_file(self, storage: Storage):
        """Test reading a file."""
        # Write file first
        content = "Test content"
        await storage.write_file("test.txt", content)

        # Read file
        read_content = await storage.read_file("test.txt")

        assert read_content == content

    @pytest.mark.asyncio
    async def test_storage_read_nonexistent_file(self, storage: Storage):
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            await storage.read_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_storage_delete_file(self, storage: Storage):
        """Test deleting a file."""
        # Write file first
        await storage.write_file("test.txt", "content")

        # Delete file
        await storage.delete_file("test.txt")

        file_path = storage.base_path / "test.txt"
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_storage_delete_nonexistent_file(self, storage: Storage):
        """Test deleting a non-existent file."""
        # Should not raise error
        await storage.delete_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_storage_file_exists(self, storage: Storage):
        """Test checking if file exists."""
        # File doesn't exist
        assert not await storage.file_exists("test.txt")

        # Create file
        await storage.write_file("test.txt", "content")

        # File exists
        assert await storage.file_exists("test.txt")

    @pytest.mark.asyncio
    async def test_storage_directory_exists(self, storage: Storage):
        """Test checking if directory exists."""
        # Directory doesn't exist
        assert not await storage.directory_exists("test_dir")

        # Create directory
        await storage.create_directory("test_dir")

        # Directory exists
        assert await storage.directory_exists("test_dir")

    @pytest.mark.asyncio
    async def test_storage_list_files(self, storage: Storage):
        """Test listing files in directory."""
        # Create files
        await storage.write_file("file1.txt", "content1")
        await storage.write_file("file2.txt", "content2")
        await storage.write_file("file3.txt", "content3")

        # List files
        files = await storage.list_files()

        assert len(files) == 3
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "file3.txt" in files

    @pytest.mark.asyncio
    async def test_storage_list_files_in_directory(self, storage: Storage):
        """Test listing files in specific directory."""
        # Create directory and files
        await storage.create_directory("subdir")
        await storage.write_file("subdir/file1.txt", "content1")
        await storage.write_file("subdir/file2.txt", "content2")
        await storage.write_file("root.txt", "content3")

        # List files in subdir
        files = await storage.list_files("subdir")

        assert len(files) == 2
        assert "file1.txt" in files
        assert "file2.txt" in files

    @pytest.mark.asyncio
    async def test_storage_list_directories(self, storage: Storage):
        """Test listing directories."""
        # Create directories
        await storage.create_directory("dir1")
        await storage.create_directory("dir2")
        await storage.write_file("file.txt", "content")

        # List directories
        dirs = await storage.list_directories()

        assert len(dirs) == 2
        assert "dir1" in dirs
        assert "dir2" in dirs

    @pytest.mark.asyncio
    async def test_storage_copy_file(self, storage: Storage):
        """Test copying a file."""
        # Create source file
        await storage.write_file("source.txt", "content")

        # Copy file
        await storage.copy_file("source.txt", "dest.txt")

        # Verify both files exist
        assert await storage.file_exists("source.txt")
        assert await storage.file_exists("dest.txt")

        # Verify content is same
        source_content = await storage.read_file("source.txt")
        dest_content = await storage.read_file("dest.txt")
        assert source_content == dest_content

    @pytest.mark.asyncio
    async def test_storage_move_file(self, storage: Storage):
        """Test moving a file."""
        # Create source file
        await storage.write_file("source.txt", "content")

        # Move file
        await storage.move_file("source.txt", "dest.txt")

        # Verify source doesn't exist
        assert not await storage.file_exists("source.txt")

        # Verify destination exists
        assert await storage.file_exists("dest.txt")

        # Verify content
        content = await storage.read_file("dest.txt")
        assert content == "content"

    @pytest.mark.asyncio
    async def test_storage_get_file_size(self, storage: Storage):
        """Test getting file size."""
        # Create file
        content = "Hello, World!"
        await storage.write_file("test.txt", content)

        # Get size
        size = await storage.get_file_size("test.txt")

        assert size == len(content.encode())

    @pytest.mark.asyncio
    async def test_storage_get_file_info(self, storage: Storage):
        """Test getting file information."""
        # Create file
        await storage.write_file("test.txt", "content")

        # Get info
        info = await storage.get_file_info("test.txt")

        assert info is not None
        assert info["name"] == "test.txt"
        assert info["size"] > 0
        assert "created_at" in info
        assert "modified_at" in info

    @pytest.mark.asyncio
    async def test_storage_delete_directory(self, storage: Storage):
        """Test deleting a directory."""
        # Create directory with files
        await storage.create_directory("test_dir")
        await storage.write_file("test_dir/file1.txt", "content1")
        await storage.write_file("test_dir/file2.txt", "content2")

        # Delete directory
        await storage.delete_directory("test_dir")

        # Verify directory is deleted
        assert not await storage.directory_exists("test_dir")

    @pytest.mark.asyncio
    async def test_storage_delete_nonempty_directory(self, storage: Storage):
        """Test deleting non-empty directory."""
        # Create directory with files
        await storage.create_directory("test_dir")
        await storage.write_file("test_dir/file.txt", "content")

        # Delete directory
        await storage.delete_directory("test_dir")

        # Verify directory is deleted
        assert not await storage.directory_exists("test_dir")

    @pytest.mark.asyncio
    async def test_storage_close(self, storage: Storage):
        """Test closing storage."""
        # Perform some operations
        await storage.write_file("test.txt", "content")

        # Close storage
        await storage.close()

        # Operations should fail after close
        with pytest.raises(Exception):
            await storage.write_file("test2.txt", "content2")

    @pytest.mark.asyncio
    async def test_storage_absolute_path(self, storage: Storage):
        """Test handling absolute paths."""
        # Write with absolute path
        file_path = storage.base_path / "test.txt"
        content = "content"

        await storage.write_file(str(file_path), content)

        # Verify
        assert file_path.exists()
        assert await storage.read_file("test.txt") == content

    @pytest.mark.asyncio
    async def test_storage_parent_directory_not_exists(self, storage: Storage):
        """Test writing file when parent directory doesn't exist."""
        # Write to nested path
        await storage.write_file("parent/child/test.txt", "content")

        # Verify all directories were created
        assert await storage.directory_exists("parent")
        assert await storage.directory_exists("parent/child")
        assert await storage.file_exists("parent/child/test.txt")

    @pytest.mark.asyncio
    async def test_storage_empty_directory(self, storage: Storage):
        """Test listing files in empty directory."""
        # Create empty directory
        await storage.create_directory("empty_dir")

        # List files
        files = await storage.list_files("empty_dir")

        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_storage_large_file(self, storage: Storage):
        """Test handling large files."""
        # Create large content
        large_content = "x" * 1024 * 1024  # 1MB

        # Write
        await storage.write_file("large.txt", large_content)

        # Read
        read_content = await storage.read_file("large.txt")

        assert read_content == large_content

    @pytest.mark.asyncio
    async def test_storage_binary_file(self, storage: Storage):
        """Test handling binary files."""
        # Create binary content
        binary_content = bytes(range(256))

        # Write
        await storage.write_file("binary.bin", binary_content)

        # Read
        read_content = await storage.read_file("binary.bin")

        assert read_content == binary_content

    @pytest.mark.asyncio
    async def test_storage_special_characters_in_filename(self, storage: Storage):
        """Test handling special characters in filename."""
        special_names = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.with.dots.txt",
        ]

        for name in special_names:
            await storage.write_file(name, "content")
            assert await storage.file_exists(name)

    @pytest.mark.asyncio
    async def test_storage_unicode_filename(self, storage: Storage):
        """Test handling unicode in filename."""
        unicode_name = "测试文件.txt"
        content = "测试内容"

        await storage.write_file(unicode_name, content)

        assert await storage.file_exists(unicode_name)
        assert await storage.read_file(unicode_name) == content

    @pytest.mark.asyncio
    async def test_storage_concurrent_operations(self, storage: Storage):
        """Test concurrent file operations."""
        # Create multiple tasks
        tasks = []
        for i in range(10):
            task = storage.write_file(f"file{i}.txt", f"content{i}")
            tasks.append(task)

        # Execute concurrently
        await asyncio.gather(*tasks)

        # Verify all files were created
        for i in range(10):
            assert await storage.file_exists(f"file{i}.txt")
            content = await storage.read_file(f"file{i}.txt")
            assert content == f"content{i}"


class TestInitStorage:
    """Test suite for init_storage function."""

    @pytest.mark.asyncio
    async def test_init_storage_creates_directory(self, temp_storage_dir: Path):
        """Test that init_storage creates directory if it doesn't exist."""
        new_dir = temp_storage_dir / "new_storage"

        storage = await init_storage(str(new_dir))

        assert new_dir.exists()
        assert new_dir.is_dir()

        await storage.close()

    @pytest.mark.asyncio
    async def test_init_storage_with_existing_directory(self, temp_storage_dir: Path):
        """Test that init_storage works with existing directory."""
        # Create directory first
        temp_storage_dir.mkdir(exist_ok=True)

        storage = await init_storage(str(temp_storage_dir))

        assert storage is not None
        assert storage.base_path == temp_storage_dir

        await storage.close()

    @pytest.mark.asyncio
    async def test_init_storage_with_none_path(self):
        """Test that init_storage uses default path when None is provided."""
        storage = await init_storage(None)

        assert storage is not None
        assert storage.base_path is not None

        await storage.close()

    @pytest.mark.asyncio
    async def test_init_storage_with_empty_string(self):
        """Test that init_storage uses default path when empty string is provided."""
        storage = await init_storage("")

        assert storage is not None
        assert storage.base_path is not None

        await storage.close()