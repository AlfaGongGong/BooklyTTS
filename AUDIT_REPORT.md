# 🔍 Audit Izvještaj — `BooklyTTS`

**Datum:** 2026-06-04 19:32:03  
**Putanja:** `/data/data/com.termux/files/home/BooklyTTS`  
**Ukupno nalaza:** 77

## 📊 Sažetak

| Status | Broj |
|--------|------|
| 🔴 Kritični | **25** |
| 🟡 Upozorenja | **21** |
| 🔵 Info | **31** |
| **Ukupno** | **77** |

---
## 🔴 ERROR (25)

### 📄 `app/cli.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 54 | `E1120` | No value for argument 'epub_path' in function call |
| 54 | `E1120` | No value for argument 'voice' in function call |
| 54 | `E1120` | No value for argument 'output' in function call |

### 📄 `app/routes.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 1 | `F401` | 'json' imported but unused |
| 1 | `F401` | 'threading' imported but unused |
| 1 | `E401` | multiple imports on one line |
| 2 | `F401` | 'flask.Response' imported but unused |
| 6 | `F401` | 'app.audio_builder.AudioBuilder' imported but unused |
| 11 | `E302` | expected 2 blank lines, found 1 |
| 16 | `E701` | multiple statements on one line (colon) |
| 18 | `E302` | expected 2 blank lines, found 1 |
| 21 | `E302` | expected 2 blank lines, found 1 |
| 24 | `E302` | expected 2 blank lines, found 1 |
| 27 | `E302` | expected 2 blank lines, found 1 |
| 30 | `E302` | expected 2 blank lines, found 1 |
| 35 | `E302` | expected 2 blank lines, found 1 |
| 37 | `E701` | multiple statements on one line (colon) |
| 39 | `E701` | multiple statements on one line (colon) |
| 52 | `E501` | line too long (124 > 120 characters) |
| 53 | `E701` | multiple statements on one line (colon) |
| 55 | `E302` | expected 2 blank lines, found 1 |
| 62 | `E302` | expected 2 blank lines, found 1 |
| 66 | `E701` | multiple statements on one line (colon) |
| 67 | `E701` | multiple statements on one line (colon) |
| 70 | `E302` | expected 2 blank lines, found 1 |

---
## 🟡 WARNING (21)

### 📄 `app/cli.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 49 | `W0718` | Catching too general exception Exception |

### 📄 `app/epub_processor.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 34 | `W0718` | Catching too general exception Exception |
| 35 | `W1203` | Use lazy % formatting in logging functions |
| 39 | `W0613` | Unused argument 'mtime' |
| 84 | `W0718` | Catching too general exception Exception |
| 85 | `W1203` | Use lazy % formatting in logging functions |
| 86 | `W0718` | Catching too general exception Exception |
| 87 | `W1203` | Use lazy % formatting in logging functions |

### 📄 `app/routes.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 1 | `W0611` | Unused import json |
| 1 | `W0611` | Unused import threading |
| 2 | `W0611` | Unused Response imported from flask |
| 6 | `W0611` | Unused AudioBuilder imported from app.audio_builder |
| 16 | `W0718` | Catching too general exception Exception |
| 53 | `W0718` | Catching too general exception Exception |

### 📄 `app/stream_api.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 94 | `W0718` | Catching too general exception Exception |

### 📄 `app/templates/convert.html`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 7 | `UI` | Anchor bez href |
| 11 | `UI` | Script bez defer/async |

### 📄 `app/templates/reader.html`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 0 | `UI-H1` | Nema <h1> |
| 142 | `UI` | Script bez defer/async |

### 📄 `sync_bidirectional.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 35 | `W0718` | Catching too general exception Exception |
| 67 | `W0718` | Catching too general exception Exception |

---
## 🔵 INFO (31)

### 📄 `app/__init__.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 15 | `C0415` | Import outside toplevel (app.routes.main_bp) |
| 16 | `C0415` | Import outside toplevel (app.stream_api.stream_bp) |

### 📄 `app/audio_builder.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 5 | `R0903` | Too few public methods (1/2) |

### 📄 `app/cli.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 5 | `C0411` | standard import "os" should be placed before first party imports "app.audio_builder.AudioBuilder", "app.epub_processor.EPUBProcessor", "app.tts_engine.TTSEngine"  |
| 6 | `C0411` | standard import "sys" should be placed before first party imports "app.audio_builder.AudioBuilder", "app.epub_processor.EPUBProcessor", "app.tts_engine.TTSEngine"  |
| 7 | `C0411` | third party import "click" should be placed before first party imports "app.audio_builder.AudioBuilder", "app.epub_processor.EPUBProcessor", "app.tts_engine.TTSEngine"  |
| 8 | `C0411` | third party import "rich.console.Console" should be placed before first party imports "app.audio_builder.AudioBuilder", "app.epub_processor.EPUBProcessor", "app.tts_engine.TTSEngine"  |

### 📄 `app/routes.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 1 | `C0410` | Multiple imports on one line (os, uuid, json, threading, time) |
| 12 | `C0415` | Import outside toplevel (zipfile) |
| 16 | `C0321` | More than one statement on a single line |
| 19 | `C0321` | More than one statement on a single line |
| 22 | `C0321` | More than one statement on a single line |
| 25 | `C0321` | More than one statement on a single line |
| 28 | `C0321` | More than one statement on a single line |
| 32 | `C0415` | Import outside toplevel (shutil) |
| 37 | `C0321` | More than one statement on a single line |
| 39 | `C0321` | More than one statement on a single line |
| 51 | `C0301` | Line too long (116/100) |
| 52 | `C0301` | Line too long (124/100) |
| 53 | `C0321` | More than one statement on a single line |
| 59 | `C0301` | Line too long (107/100) |
| 66 | `C0321` | More than one statement on a single line |
| 67 | `C0321` | More than one statement on a single line |
| 76 | `C0301` | Line too long (102/100) |
| 79 | `C0301` | Line too long (103/100) |

### 📄 `app/stream_api.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 59 | `R1732` | Consider using 'with' for resource-allocating operations |
| 126 | `R1732` | Consider using 'with' for resource-allocating operations |

### 📄 `app/templates/index.html`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 0 | `UI-HEADING` | Preskočen heading h1→h3 |

### 📄 `app/tts_engine.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 46 | `C0415` | Import outside toplevel (edge_tts) |
| 49 | `R1732` | Consider using 'with' for resource-allocating operations |
| 75 | `R1732` | Consider using 'with' for resource-allocating operations |

---
*Generisano s Audit Pipeline · 2026-06-04 19:32:03*