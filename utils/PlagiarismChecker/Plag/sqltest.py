import psycopg2
import sys, os
import numpy as np
import pandas as pd

PGHOST = '203.250.32.197'
PGDB = 'onlinejudge'
PGUSER = 'onlinejudge'
PGPASSWD = 'onlinejudge'

conn_str = "host=" + PGHOST + " port=" + "5432" + " dbname=" + PGDB + " user=" + PGUSER + " password=" + PGPASSWD
conn = psycopg2.connect(conn_str)
print("Connected!!")

cursor = conn.cursor()


def load_data(table):
    sql_command = "SELECT * FROM {};".format(str(table))
    print(sql_command)

    data = pd.read_sql(sql_command, conn)

    print(data.columns)
    print(data['code'])

    return (data)


load_data('submission')
