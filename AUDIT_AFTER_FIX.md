# 🔍 Audit Izvještaj — `BooklyTTS`

**Datum:** 2026-06-04 17:57:18  
**Putanja:** `/data/data/com.termux/files/home/BooklyTTS`  
**Ukupno nalaza:** 49

## 📊 Sažetak

| Status | Broj |
|--------|------|
| 🔴 Kritični | **4** |
| 🟡 Upozorenja | **20** |
| 🔵 Info | **25** |
| **Ukupno** | **49** |

---
## 🔴 ERROR (4)

### 📄 `app/cli.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 54 | `E1120` | No value for argument 'epub_path' in function call |
| 54 | `E1120` | No value for argument 'voice' in function call |
| 54 | `E1120` | No value for argument 'output' in function call |

### 📄 `app/routes.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 267 | `E1101` | Instance of 'NameReplacer' has no 'preview' member |

---
## 🟡 WARNING (20)

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
| 24 | `W0718` | Catching too general exception Exception |
| 76 | `W0718` | Catching too general exception Exception |
| 132 | `W0718` | Catching too general exception Exception |
| 143 | `W0718` | Catching too general exception Exception |

### 📄 `app/stream_api.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 79 | `W0718` | Catching too general exception Exception |
| 163 | `W0718` | Catching too general exception Exception |

### 📄 `app/templates/convert.html`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 7 | `UI` | Anchor bez href |
| 11 | `UI` | Script bez defer/async |

### 📄 `app/templates/reader.html`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 0 | `UI-H1` | Nema <h1> |
| 153 | `UI` | Script bez defer/async |

### 📄 `sync_bidirectional.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 35 | `W0718` | Catching too general exception Exception |
| 67 | `W0718` | Catching too general exception Exception |

---
## 🔵 INFO (25)

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
| 2 | `C0411` | standard import "os" should be placed before first party import "app.replacer.NameReplacer"  |
| 3 | `C0411` | standard import "uuid" should be placed before first party import "app.replacer.NameReplacer"  |
| 4 | `C0411` | standard import "json" should be placed before first party import "app.replacer.NameReplacer"  |
| 5 | `C0411` | standard import "threading" should be placed before first party import "app.replacer.NameReplacer"  |
| 6 | `C0411` | standard import "time" should be placed before first party import "app.replacer.NameReplacer"  |
| 7 | `C0411` | third party import "flask.Blueprint" should be placed before first party import "app.replacer.NameReplacer"  |
| 9 | `C0411` | third party import "werkzeug.utils.secure_filename" should be placed before first party import "app.replacer.NameReplacer"  |
| 10 | `C0412` | Imports from package app are not grouped |
| 19 | `C0415` | Import outside toplevel (zipfile) |
| 35 | `C0415` | Import outside toplevel (shutil) |
| 135 | `C0415` | Import outside toplevel (app.database.save_conversion) |
| 211 | `C0415` | Import outside toplevel (app.database.get_history) |

### 📄 `app/stream_api.py`
| Linija | Kod | Poruka |
|--------|-----|--------|
| 52 | `R1732` | Consider using 'with' for resource-allocating operations |
| 104 | `R1732` | Consider using 'with' for resource-allocating operations |

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
*Generisano s Audit Pipeline · 2026-06-04 17:57:18*