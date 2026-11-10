# PDF Editor Pro

កម្មវិធីកែ PDF ឥតគិតថ្លៃសម្រាប់ Windows និង Mac គាំទ្រអក្សរខ្មែរ។
Free PDF editor for Windows and macOS with Khmer text support, by Cambo Ads.

## ទាញយក / Download

ទាញយក **PDF Editor Pro v….exe** ពីទំព័រ [Releases](https://github.com/channaofficial1996/PDF-Editor-Pro/releases/latest) បើកវា រួចចុច **Install**។
កម្មវិធីនឹងបង្កើត shortcut លើ Desktop ហើយអ្នកអាចរកវាតាម Windows search បាន។ បើចង់ដំឡើងតាមវិធីធម្មតា ក៏អាចប្រើ **PDF Editor Pro Setup** បានដែរ។

កម្មវិធីនេះមិនទាន់មានហត្ថលេខា Code Signing ទេ៖

- បើឃើញ **Windows protected your PC** ចុច **More info → Run anyway**។
- បើ **Smart App Control** កំពុងបើក Windows នឹងទប់ស្កាត់កម្មវិធី។

The app is not code signed yet. If SmartScreen warns you, choose **More info → Run anyway**. Windows blocks it
while Smart App Control is on.

### Mac

ទាញយក **PDF Editor Pro v… macOS Apple Silicon.dmg** (Mac M1/M2/M3/M4) ឬ **macOS Intel.dmg** (Mac ចាស់) ពីទំព័រ
[Releases](https://github.com/channaofficial1996/PDF-Editor-Pro/releases/latest) បើក .dmg រួចអូស **PDF Editor Pro** ចូល **Applications**។
(មើលប្រភេទ Mac៖  → About This Mac → Chip ឬ Processor)

ដោយសារកម្មវិធីមិនទាន់មានហត្ថលេខា Apple ពេលបើកលើកដំបូង Mac នឹងប្រាប់ថាមិនអាចបើកបាន៖

1. ចុច **Done** (កុំចុច Move to Trash)។
2. ចូល **System Settings → Privacy & Security** រំកិលចុះក្រោម ចុច **Open Anyway** រួចបញ្ចូលពាក្យសម្ងាត់ Mac។

ធ្វើតែម្តងប៉ុណ្ណោះ។ ការ Update លើ Mac៖ ពេលមានកំណែថ្មី កម្មវិធីនឹងបើកទំព័រ Releases ឱ្យទាញយក .dmg ថ្មី។

On a Mac, download the Apple Silicon or Intel `.dmg`, open it and drag **PDF Editor Pro** into **Applications**. The
app is not signed by Apple, so the first launch is refused: click **Done**, then go to **System Settings → Privacy &
Security** and click **Open Anyway**. Updates open the Releases page so you can download the new `.dmg`.

## មុខងារ / Features

- កែអក្សរក្នុង PDF និងបន្ថែមអក្សរ រួមទាំងអក្សរខ្មែរ
- Annotation, signature, whiteout, redaction, link និង crop
- គ្រប់គ្រងទំព័រ, merge/split, watermark, page numbers
- Forms, bookmarks, passwords, export និង print
- Update ពីក្នុងកម្មវិធី (ប៊ូតុង Update ឬ Help → Check for updates)

## Run from source

Requires Windows or macOS and Python 3.12.

```
pip install pymupdf==1.25.5 pyside6 pyinstaller
python pdf_editor.py
```

## Build and release

Bump `VERSION` in `version.py` and add a `CHANGELOG.md` entry first.

- `python build.py` builds the EXE and the installer into `dist/` (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)).
- `python release.py` also publishes them as a GitHub Release (needs the [GitHub CLI](https://cli.github.com/)).
  Commit and push first: GitHub Actions ([macos.yml](.github/workflows/macos.yml)) then builds the macOS `.dmg`
  files from the same commit and adds them to the release.
- On a Mac, `python build.py` builds `dist/PDF Editor Pro.app` and the `.dmg` locally (`pip install pillow` too).

## License

Copyright © 2026 Cambo Ads. Licensed under the [GNU Affero General Public License v3.0](LICENSE).

Built with [PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0) and [PySide6](https://doc.qt.io/qtforpython-6/) (LGPL-3.0).
