# The purpose of this database is to edit categories more easily. The database
# is not implemented (TODO!) to the main module which still uses json (that's
# why we generate a new list of dicts)

import json
import os
import sqlite3
from operator import itemgetter
from pathlib import Path

import requests
import tmdbsimple as tmdb


SUBTITLES = os.environ.get("HOME") + "/subtitles"
RADARR = os.environ.get("RADARR")
FILM_COLLECTION = os.environ.get("FILM_COLLECTION")
MOVIE_JSON = os.environ.get("MOVIE_JSON")
TV_COLLECTION = os.environ.get("TV_COLLECTION")
TMDB_KEY = os.environ.get("TMDB")
tmdb.API_KEY = TMDB_KEY


def create_table(conn):
    try:
        conn.execute(
            """CREATE TABLE MOVIES
            (title TEXT NOT NULL,
            og_title TEXT NOT NULL,
            year INT NOT NULL,
            director TEXT NOT NULL,
            country TEXT NOT NULL,
            category TEXT NOT NULL,
            poster TEXT NOT NULL,
            backdrop TEXT NOT NULL,
            path TEXT NOT NULL,
            subtitle TEXT NOT NULL);"""
        )
        conn.execute("CREATE UNIQUE INDEX title_og ON MOVIES (title,og_title);")
        print("Table created successfully")
    except sqlite3.OperationalError as e:
        print(e)


def insert_into_table(conn, values):
    sql = """INSERT INTO MOVIES
    (title, og_title, year, director, country, category,
    poster, backdrop, path, subtitle)
    VALUES (?,?,?,?,?,?,?,?,?,?)"""
    cur = conn.cursor()
    try:
        cur.execute(sql, values)
    except sqlite3.IntegrityError:
        print(
            "{} ({}) has been detected as a duplicate title. Do something about it!".format(
                values[0], values[8]
            )
        )
    finally:
        conn.commit()


def generate_json(conn):
    print("Generating json...")
    cursor = conn.execute("SELECT * from MOVIES")
    new_json = []
    for i in cursor:
        new_json.append(
            {
                "title": i[0],
                "original_title": i[1],
                "year": i[2],
                "director": i[3],
                "country": i[4],
                "category": i[5],
                "poster": i[6],
                "path": i[8],
                "subtitle": i[9],
            }
        )
    with open(MOVIE_JSON, "w", encoding="utf-8") as f:
        sorted_list = sorted(new_json, key=itemgetter("title"))
        json.dump(sorted_list, f, ensure_ascii=False, indent=4)
        print("Ok")


def is_not_missing(real_path, path_list):
    for i in path_list:
        if i == real_path:
            return True


def missing_files(conn, json_paths):
    cursor = conn.execute("SELECT path from MOVIES")
    for i in cursor:
        if is_not_missing(i[0], json_paths):
            continue
        else:
            print("Deleting missing data with file: {}".format(i[0]))
            cursor.execute("DELETE FROM MOVIES WHERE path=?", (i))
            conn.commit()


def value_exists(conn, path):
    c = conn.cursor()
    c.execute("SELECT 1 FROM MOVIES WHERE path=? LIMIT 1", (path,))
    return c.fetchone() is not None


def collect_movies(conn, radarr_json):
    print("Total files: {}".format(len(radarr_json)))
    for i in radarr_json:
        if i["hasFile"]:
            filename = i["movieFile"]["path"]
            if value_exists(conn, filename):
                continue
            to_srt = Path(filename).with_suffix("")
            srt = "{}.{}".format(to_srt, "en.srt")
            movie = tmdb.Movies(i["tmdbId"])
            movie.info()
            country_list = ", ".join([i["name"] for i in movie.production_countries])
            IMAGE_BASE = "https://image.tmdb.org/t/p/original"
            movie.credits()
            dirs = [m["name"] for m in movie.crew if m["job"] == "Director"]
            values = (
                movie.title,
                str(movie.original_title) if movie.original_title else movie.title,
                movie.release_date.split("-")[0],
                ", ".join(dirs),
                country_list,
                "Certified Kino",
                IMAGE_BASE + str(movie.poster_path) if movie.poster_path else "Unknown",
                IMAGE_BASE + str(movie.backdrop_path)
                if movie.backdrop_path
                else "Unknown",
                filename,
                srt,
            )
            insert_into_table(conn, values)
            print("Added: {}".format(movie.title))


def get_json():
    url = "http://radarr.caretas.club/api/v3/movie?apiKey=" + RADARR
    r = requests.get(url)
    return json.loads(r.content)


def main():
    radarr_json = get_json()
    conn = sqlite3.connect(os.environ.get("KINOBASE"))
    create_table(conn)
    missing_files(conn, [i["movieFile"]["path"] for i in radarr_json if i["hasFile"]])
    collect_movies(conn, radarr_json)
    generate_json(conn)
    conn.close()


main()
