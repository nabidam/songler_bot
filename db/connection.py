import mysql.connector

from config.env import *


def getDb():
    db = mysql.connector.connect(
        host="localhost",
        user=DB_USERNAME,
        password=DB_PASSWORD,
        database=DB_DATABASE
    )

    return db


def executeQuery():
    try:
        db = getDb()
        dbcursor = db.cursor()
        dbcursor.executemany(sql_string, data_to_insert)

        db.commit()

        sql_select_query = "SELECT id, song, artist FROM songs ORDER BY created_at DESC LIMIT 5 OFFSET %s"
        dbcursor.execute(sql_select_query, [page * 5])
        # get all records
        records = dbcursor.fetchall()

        for row in records:
            item = {
                "id": row[0],
                "song": row[1],
                "artist": row[2],
            }

            musics.append(item)

    except mysql.connector.Error as error:
        logger.error(error)
    finally:
        if db.is_connected():
            dbcursor.close()
            db.close()
    return musics
