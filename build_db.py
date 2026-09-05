import argparse
import json
import os
import sqlite3
import sys

def init_db(con):
    cur = con.cursor()
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA journal_mode = MEMORY;")
    cur.execute("PRAGMA cache_size = 100000;")
    cur.execute("PRAGMA temp_store = MEMORY;")
    
    cur.execute("""
    CREATE TABLE poets (
        id INTEGER PRIMARY KEY,
        name TEXT,
        nickname TEXT,
        description TEXT,
        full_url TEXT,
        image_url TEXT,
        birth_year INTEGER,
        death_year INTEGER,
        birth_place TEXT,
        death_place TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY,
        poet_id INTEGER,
        parent_id INTEGER,
        title TEXT,
        full_url TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE poems (
        id INTEGER PRIMARY KEY,
        cat_id INTEGER,
        title TEXT,
        full_title TEXT,
        full_url TEXT,
        rhyme_letters TEXT,
        source_name TEXT,
        poem_summary TEXT,
        metre_id INTEGER,
        metre_rhythm TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE verses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poem_id INTEGER,
        v_order INTEGER,
        couplet_index INTEGER,
        position TEXT,
        text TEXT
    );
    """)
    con.commit()

def process_data(data_dir, con):
    poets_dir = os.path.join(data_dir, "poets")
    if not os.path.exists(poets_dir):
        poets_dir = data_dir

    cur = con.cursor()
    poet_rows = []
    cat_rows = []
    poem_rows = []
    verse_rows = []

    for root, dirs, files in os.walk(poets_dir):
        for f in files:
            if not f.endswith(".json"):
                continue
            
            fpath = os.path.join(root, f)
            
            if f == "poet.json":
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        d = json.load(fp)
                    poet_rows.append((
                        d.get("Id"),
                        d.get("Name") or "",
                        d.get("Nickname"),
                        d.get("Description"),
                        d.get("FullUrl"),
                        d.get("ImageUrl"),
                        d.get("BirthYearInLHijri"),
                        d.get("DeathYearInLHijri"),
                        d.get("BirthPlace"),
                        d.get("DeathPlace")
                    ))
                except Exception:
                    pass
            elif f == "_cat.json":
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        d = json.load(fp)
                    cat_rows.append((
                        d.get("Id"),
                        d.get("PoetId"),
                        d.get("ParentId"),
                        d.get("Title") or "",
                        d.get("FullUrl")
                    ))
                except Exception:
                    pass
            elif f != "manifest.json":
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        d = json.load(fp)
                    poem_id = d.get("Id")
                    if poem_id is None:
                        continue
                    metre = d.get("Metre") or {}
                    poem_rows.append((
                        poem_id,
                        d.get("CatId"),
                        d.get("Title") or "",
                        d.get("FullTitle"),
                        d.get("FullUrl"),
                        d.get("RhymeLetters"),
                        d.get("SourceName"),
                        d.get("PoemSummary"),
                        metre.get("Id"),
                        metre.get("Rhythm")
                    ))
                    for v in d.get("Verses", []):
                        verse_rows.append((
                            poem_id,
                            v.get("VOrder"),
                            v.get("CoupletIndex"),
                            v.get("Position"),
                            v.get("Text") or ""
                        ))
                except Exception:
                    pass

            if len(poem_rows) >= 5000:
                cur.executemany("INSERT OR IGNORE INTO poems VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", poem_rows)
                cur.executemany("INSERT INTO verses (poem_id, v_order, couplet_index, position, text) VALUES (?, ?, ?, ?, ?)", verse_rows)
                con.commit()
                poem_rows.clear()
                verse_rows.clear()

    if poet_rows:
        cur.executemany("INSERT OR IGNORE INTO poets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", poet_rows)
    if cat_rows:
        cur.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?, ?, ?, ?)", cat_rows)
    if poem_rows:
        cur.executemany("INSERT OR IGNORE INTO poems VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", poem_rows)
    if verse_rows:
        cur.executemany("INSERT INTO verses (poem_id, v_order, couplet_index, position, text) VALUES (?, ?, ?, ?, ?)", verse_rows)
    con.commit()

def merge_legacy_db(legacy_db_path, con):
    if not legacy_db_path or not os.path.exists(legacy_db_path):
        return

    target_poet_ids = (
        501, 502, 503, 504, 505, 506, 507, 510, 511, 512,
        513, 514, 515, 516, 517, 518, 603, 608, 609, 610,
        616, 618
    )

    src = sqlite3.connect(legacy_db_path)
    src_cur = src.cursor()
    dest_cur = con.cursor()

    placeholders = ",".join("?" for _ in target_poet_ids)
    src_cur.execute(f"SELECT id, name, description FROM poet WHERE id IN ({placeholders})", target_poet_ids)
    poet_rows = [(r[0], r[1], None, r[2], None, None, None, None, None, None) for r in src_cur.fetchall()]
    dest_cur.executemany("INSERT OR IGNORE INTO poets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", poet_rows)

    src_cur.execute(f"SELECT id, poet_id, parent_id, text, url FROM cat WHERE poet_id IN ({placeholders})", target_poet_ids)
    cat_rows = [(r[0], r[1], r[2], r[3] or "", r[4]) for r in src_cur.fetchall()]
    dest_cur.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?, ?, ?, ?)", cat_rows)

    src_cur.execute(f"""
        SELECT pm.id, pm.cat_id, pm.title, pm.url
        FROM poem pm
        JOIN cat c ON pm.cat_id = c.id
        WHERE c.poet_id IN ({placeholders})
    """, target_poet_ids)
    poem_rows = [(r[0], r[1], r[2] or "", r[2], r[3], None, None, None, None, None) for r in src_cur.fetchall()]
    dest_cur.executemany("INSERT OR IGNORE INTO poems VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", poem_rows)

    src_cur.execute(f"""
        SELECT v.poem_id, v.vorder, v.position, v.text
        FROM verse v
        JOIN poem pm ON v.poem_id = pm.id
        JOIN cat c ON pm.cat_id = c.id
        WHERE c.poet_id IN ({placeholders})
        ORDER BY v.poem_id, v.vorder
    """, target_poet_ids)

    verse_rows = []
    while True:
        batch = src_cur.fetchmany(5000)
        if not batch:
            break
        for r in batch:
            poem_id = r[0]
            v_order = r[1]
            couplet_index = v_order // 2
            position = str(r[2]) if r[2] is not None else "0"
            text = r[3] or ""
            verse_rows.append((poem_id, v_order, couplet_index, position, text))
        dest_cur.executemany("INSERT INTO verses (poem_id, v_order, couplet_index, position, text) VALUES (?, ?, ?, ?, ?)", verse_rows)
        con.commit()
        verse_rows.clear()

    con.commit()
    src.close()

def build_indices_and_fts(con):
    cur = con.cursor()
    cur.execute("CREATE INDEX idx_categories_poet_id ON categories(poet_id);")
    cur.execute("CREATE INDEX idx_categories_parent_id ON categories(parent_id);")
    cur.execute("CREATE INDEX idx_poems_cat_id ON poems(cat_id);")
    cur.execute("CREATE INDEX idx_verses_poem_id ON verses(poem_id);")
    cur.execute("CREATE INDEX idx_verses_couplet ON verses(poem_id, couplet_index);")
    
    cur.execute("CREATE VIRTUAL TABLE verses_fts USING fts5(text, poem_id UNINDEXED, content='verses', content_rowid='id', tokenize='unicode61');")
    cur.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild');")
    cur.execute("PRAGMA optimize;")
    con.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="ganjoor-data-main")
    parser.add_argument("--legacy-db", default=None)
    parser.add_argument("--output", default="ganjoor.db")
    args = parser.parse_args()

    if os.path.exists(args.output):
        os.remove(args.output)

    con = sqlite3.connect(args.output)
    init_db(con)
    if os.path.exists(args.data_dir):
        process_data(args.data_dir, con)
    if args.legacy_db:
        merge_legacy_db(args.legacy_db, con)
    build_indices_and_fts(con)
    con.close()

if __name__ == "__main__":
    main()
