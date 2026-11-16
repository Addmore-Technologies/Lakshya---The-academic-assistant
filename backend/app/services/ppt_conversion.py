"""Convert legacy PowerPoint (.ppt) files into PPTX."""

import subprocess
import tempfile
from pathlib import Path


def convert_ppt_to_pptx(file_bytes: bytes) -> bytes:
    """Convert PPT bytes to PPTX using LibreOffice."""

    if not file_bytes:
        raise ValueError("The PPT file is empty.")

    # Legacy binary PowerPoint files use OLE compound storage.
    if not file_bytes.startswith(
        bytes.fromhex("D0CF11E0A1B11AE1")
    ):
        raise ValueError("Invalid legacy PPT file.")

    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        source = folder / "presentation.ppt"
        destination = folder / "presentation.pptx"
        output_dir = folder / "converted"
        output_dir.mkdir()

        source.write_bytes(file_bytes)

        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "-env:UserInstallation=file://"
                    + str(folder / "lo-profile"),
                    "--headless",
                    "--convert-to",
                    "pptx",
                    "--outdir",
                    str(output_dir),
                    str(source),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "LibreOffice is not installed on the server."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "PowerPoint conversion timed out."
            ) from exc

        destination = output_dir / "presentation.pptx"

        if result.returncode != 0 or not destination.is_file():
            raise ValueError(
                "Could not convert the PPT file to PPTX."
            )

        converted = destination.read_bytes()

        if not converted.startswith(b"PK"):
            raise ValueError(
                "Converted PowerPoint file is invalid."
            )

        return converted
