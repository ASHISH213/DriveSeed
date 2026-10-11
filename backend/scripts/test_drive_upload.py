"""Demonstration and verification script for DriveApiStorage 200 MB file upload."""

import argparse
import asyncio
import hashlib
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Add parent directory to path so imports work when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.user import User
from app.services.drive import DriveApiStorage
from tests.fakes.fake_google_drive import FakeGoogleDriveService


def generate_test_file(target_path: Path, size_mb: int = 200) -> str:
    """Generate a test file with deterministic pattern and return its MD5."""
    print(f"[*] Generating {size_mb} MB test file at {target_path}...")
    chunk_pattern = b"DriveSeed 200MB Verification Pattern Block!\n" * 1024  # ~45 KB
    total_bytes = size_mb * 1024 * 1024
    bytes_written = 0
    hasher = hashlib.md5()

    with target_path.open("wb") as f:
        while bytes_written < total_bytes:
            to_write = min(len(chunk_pattern), total_bytes - bytes_written)
            f.write(chunk_pattern[:to_write])
            hasher.update(chunk_pattern[:to_write])
            bytes_written += to_write

    md5_digest = hasher.hexdigest()
    print(f"[+] File generated. Size: {target_path.stat().st_size:,} bytes, MD5: {md5_digest}")
    return md5_digest


async def run_verification(size_mb: int = 200, simulated: bool = True) -> bool:
    """Run DriveApiStorage upload verification for a 200 MB file."""
    print("=" * 65)
    print(f"DriveSeed DriveApiStorage Verification ({size_mb} MB Test File)")
    print(f"Mode: {'Simulated Fake Drive' if simulated else 'Live Google Drive'}")
    print("=" * 65)

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / f"driveseed_test_{size_mb}mb.bin"
        local_md5 = generate_test_file(test_file, size_mb=size_mb)
        local_size = test_file.stat().st_size

        if simulated:
            fake_drive = FakeGoogleDriveService()
            storage = DriveApiStorage(
                client_factory=lambda _u: fake_drive,
                chunk_size=16 * 1024 * 1024,  # 16 MB chunks
            )
            user = User(
                id=uuid.uuid4(),
                google_sub="test_sub_verification",
                email="verification@driveseed.io",
                drive_refresh_token_enc=None,
                drive_root_folder_id=None,
                created_at=datetime.now(UTC),
            )
        else:
            storage = DriveApiStorage(chunk_size=16 * 1024 * 1024)
            # In live mode, expects active user in database with valid refresh token
            raise NotImplementedError("Live mode requires configured user credentials.")

        # 1. Ensure Root
        print("\n[*] Step 1: Ensuring root folder 'DriveSeed' exists...")
        root_id = await storage.ensure_root(user)
        print(f"[+] Root folder ID: {root_id}")

        # 2. Resumable Upload
        print(f"\n[*] Step 2: Uploading {size_mb} MB test file in 16 MB resumable chunks...")
        start_time = time.time()
        last_pct = -1

        def on_progress(bytes_uploaded: int, total_bytes: int) -> None:
            nonlocal last_pct
            pct = int((bytes_uploaded / total_bytes) * 100) if total_bytes > 0 else 0
            if pct != last_pct and (pct % 10 == 0 or pct == 100):
                mb_uploaded = bytes_uploaded / (1024 * 1024)
                mb_total = total_bytes / (1024 * 1024)
                print(f"    Progress: {pct:3d}% ({mb_uploaded:6.1f} MB / {mb_total:.1f} MB)")
                last_pct = pct

        stored_file = await storage.upload_file(
            user=user,
            parent_id=root_id,
            local_path=test_file,
            on_progress=on_progress,
        )

        elapsed = time.time() - start_time
        mb_rate = stored_file.size_bytes / (1024 * 1024) / elapsed if elapsed > 0 else 0
        print(f"[+] Upload completed in {elapsed:.2f}s ({mb_rate:.1f} MB/s)")

        # 3. Verification
        print("\n[*] Step 3: Verifying integrity and metadata...")
        print(f"    Stored File ID : {stored_file.id}")
        print(f"    Remote Size    : {stored_file.size_bytes:,} bytes (expected: {local_size:,})")
        print(f"    Remote MD5     : {stored_file.md5} (expected: {local_md5})")

        size_match = stored_file.size_bytes == local_size
        md5_match = stored_file.md5 == local_md5

        if size_match and md5_match:
            print("\n[SUCCESS] Verification PASSED: Both file size and MD5 match perfectly!")
        else:
            print(f"\n[FAILURE] Verification FAILED: size={size_match}, md5={md5_match}")
            return False

        # 4. Clean up test file from Drive
        print("\n[*] Step 4: Cleaning up test file from Drive...")
        await storage.delete(user, stored_file.id)
        print("[+] Test file deleted successfully.")

    print("\n" + "=" * 65)
    print("VERIFICATION COMPLETE: ALL CHECKS PASSED")
    print("=" * 65)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DriveApiStorage 200 MB upload verification script"
    )
    parser.add_argument("--size-mb", type=int, default=200, help="File size in MB (default: 200)")
    parser.add_argument(
        "--simulated", action="store_true", default=True, help="Run with fake Drive"
    )
    args = parser.parse_args()

    success = asyncio.run(run_verification(size_mb=args.size_mb, simulated=args.simulated))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
