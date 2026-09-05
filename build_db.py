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
        name TEXT NOT NULL,
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
        title TEXT NOT NULL,
        full_url TEXT,
        FOREIGN KEY (poet_id) REFERENCES poets(id),
        FOREIGN KEY (parent_id) REFERENCES categories(id)
    );
    """)
    cur.execute("""
    CREATE TABLE poems (
        id INTEGER PRIMARY KEY,
        cat_id INTEGER,
        title TEXT NOT NULL,
        full_title TEXT,
        full_url TEXT,
        rhyme_letters TEXT,
        source_name TEXT,
        poem_summary TEXT,
        metre_id INTEGER,
        metre_rhythm TEXT,
        FOREIGN KEY (cat_id) REFERENCES categories(id)
    );
    """)
    cur.execute("""
    CREATE TABLE verses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poem_id INTEGER NOT NULL,
        v_order INTEGER NOT NULL,
        couplet_index INTEGER NOT NULL,
        position TEXT,
        text TEXT NOT NULL,
        FOREIGN KEY (poem_id) REFERENCES poems(id)
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

    cur.execute("CREATE INDEX idx_categories_poet_id ON categories(poet_id);")
    cur.execute("CREATE INDEX idx_categories_parent_id ON categories(parent_id);")
    cur.execute("CREATE INDEX idx_poems_cat_id ON poems(cat_id);")
    cur.execute("CREATE INDEX idx_verses_poem_id ON verses(poem_id);")
    cur.execute("CREATE INDEX idx_verses_couplet ON verses(poem_id, couplet_index);")
    
    cur.execute("CREATE VIRTUAL TABLE verses_fts USING fts5(text, poem_id UNINDEXED, content='verses', content_rowid='id', tokenize='unicode61');")
    cur.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild');")
    con.commit()

    cur.execute("PRAGMA optimize;")
    con.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="ganjoor-data-main")
    parser.add_argument("--output", default="ganjoor.db")
    args = parser.parse_args()

    if os.path.exists(args.output):
        os.remove(args.output)

    con = sqlite3.connect(args.output)
    init_db(con)
    process_data(args.data_dir, con)
    con.close()

if __name__ == "__main__":
    main()
