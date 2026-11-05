# PDF Editor Pro

កម្មវិធីកែ PDF ឥតគិតថ្លៃសម្រាប់ Windows គាំទ្រអក្សរខ្មែរ។
Free PDF editor for Windows with Khmer text support, by Cambo Ads.

## ទាញយក / Download

ទាញយក **PDF Editor Pro Setup** ពីទំព័រ [Releases](https://github.com/channaofficial1996/PDF-Editor-Pro/releases/latest) រួចដំឡើង។
Setup បង្កើត shortcut លើ Desktop ហើយអ្នកអាចរកកម្មវិធីតាម Windows search បាន។

កម្មវិធីនេះមិនទាន់មានហត្ថលេខា Code Signing ទេ៖

- បើឃើញ **Windows protected your PC** ចុច **More info → Run anyway**។
- បើ **Smart App Control** កំពុងបើក Windows នឹងទប់ស្កាត់កម្មវិធី។

The app is not code signed yet. If SmartScreen warns you, choose **More info → Run anyway**. Windows blocks it
while Smart App Control is on.

## មុខងារ / Features

- កែអក្សរក្នុង PDF និងបន្ថែមអក្សរ រួមទាំងអក្សរខ្មែរ
- Annotation, signature, whiteout, redaction, link និង crop
- គ្រប់គ្រងទំព័រ, merge/split, watermark, page numbers
- Forms, bookmarks, passwords, export និង print
- Update ពីក្នុងកម្មវិធី (ប៊ូតុង Update ឬ Help → Check for updates)

## Run from source

Requires Windows and Python 3.12.

```
pip install pymupdf==1.25.5 pyside6 pyinstaller
python pdf_editor.py
```

## Build and release

Bump `VERSION` in `version.py` and add a `CHANGELOG.md` entry first.

- `python build.py` builds the EXE and the installer into `dist/` (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)).
- `python release.py` also publishes them as a GitHub Release (needs the [GitHub CLI](https://cli.github.com/)).

## License

Copyright © 2026 Cambo Ads. Licensed under the [GNU Affero General Public License v3.0](LICENSE).

Built with [PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0) and [PySide6](https://doc.qt.io/qtforpython-6/) (LGPL-3.0).
