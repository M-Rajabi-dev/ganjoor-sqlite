# Ganjoor SQLite Database

This repository automatically builds and maintains a standalone, indexed SQLite database from the official [ganjoor/ganjoor-data](https://github.com/ganjoor/ganjoor-data) dataset.

A scheduled GitHub Actions workflow checks for new commits in `ganjoor/ganjoor-data` daily. Whenever upstream changes occur, it builds a fresh SQLite database and publishes it under [Releases](../../releases).

## Download

Get the latest build from the [Releases](../../releases/latest) page:
- `ganjoor.db`: Raw, uncompressed SQLite database (ready for direct use).
- `ganjoor.db.zip`: Standard ZIP archive (recommended for Windows/macOS native extraction).
- `ganjoor.db.7z`: Compressed with 7-Zip LZMA2 (maximum compression, smallest file size).

To decompress:
```bash
# Using unzip
unzip ganjoor.db.zip

# Or using 7z
7z x ganjoor.db.7z
```

## Database Schema

The database consists of relational tables and a full-text search index:

### `poets`
- `id` (INTEGER PRIMARY KEY)
- `name` (TEXT)
- `nickname` (TEXT)
- `description` (TEXT)
- `full_url` (TEXT)
- `image_url` (TEXT)
- `birth_year` (INTEGER)
- `death_year` (INTEGER)
- `birth_place` (TEXT)
- `death_place` (TEXT)

### `categories`
- `id` (INTEGER PRIMARY KEY)
- `poet_id` (INTEGER, REFERENCES poets)
- `parent_id` (INTEGER, REFERENCES categories)
- `title` (TEXT)
- `full_url` (TEXT)

### `poems`
- `id` (INTEGER PRIMARY KEY)
- `cat_id` (INTEGER, REFERENCES categories)
- `title` (TEXT)
- `full_title` (TEXT)
- `full_url` (TEXT)
- `rhyme_letters` (TEXT)
- `source_name` (TEXT)
- `poem_summary` (TEXT)
- `metre_id` (INTEGER)
- `metre_rhythm` (TEXT)

### `verses`
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `poem_id` (INTEGER, REFERENCES poems)
- `v_order` (INTEGER)
- `couplet_index` (INTEGER)
- `position` (TEXT: 'Right', 'Left', 'Single', etc.)
- `text` (TEXT)

### `verses_fts`
A virtual table using SQLite FTS5 (unicode61 tokenizer) indexing `verses.text` for sub-millisecond search across all verses.

## Query Examples

### List all poets
```sql
SELECT id, name, nickname, death_year FROM poets ORDER BY id;
```

### Get poems for a specific category
```sql
SELECT id, title, full_title FROM poems WHERE cat_id = 24 ORDER BY id;
```

### Full-Text Search on Verses
```sql
SELECT v.poem_id, p.full_title, v.text
FROM verses_fts f
JOIN verses v ON f.rowid = v.id
JOIN poems p ON v.poem_id = p.id
WHERE f.verses_fts MATCH 'ساقی'
LIMIT 20;
```

## Local Build

To generate the database locally:

```bash
curl -sSL -o ganjoor-data.tar.gz https://github.com/ganjoor/ganjoor-data/archive/refs/heads/main.tar.gz
tar -xzf ganjoor-data.tar.gz
python build_db.py --data-dir ganjoor-data-main --output ganjoor.db
```
