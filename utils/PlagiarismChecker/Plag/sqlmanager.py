import psycopg2
import sys, os
import numpy as np
import pandas as pd


class SQLManager:
    def __init__(self):
        self.PGHOST = '203.250.32.197'
        #self.PGHOST = 'localhost'
        self.PGDB = 'onlinejudge'
        self.PGUSER = 'onlinejudge'
        self.PGPASSWD = 'onlinejudge'
        self.connectOJSQL()

        self.sub_tablename = 'submission'

    def connectOJSQL(self):
        conn_str = "host=" + self.PGHOST + " port=" + "5432" + " dbname=" + self.PGDB + " user=" + self.PGUSER + " password=" + self.PGPASSWD
        self.conn = psycopg2.connect(conn_str)
        print("Connected!!")
        self.cursor = self.conn.cursor()

    def load_data(self, table, lid=-1, cid=-1, pid=-1, hasUser=False, SelectDataQuery=None):
        if hasUser:
            qstr = str(table) + ", " + "public.user"
        else:
            qstr = str(table)
        comma = ""

        if pid != -1 or cid != -1 or lid != -1:
            qstr = qstr + " where"

        if pid != -1:
            qstr = qstr + " problem_id=%s" % str(pid)
            comma = " and"

        if lid != -1:
            qstr = qstr + comma + " lecture_id=%s" % str(lid)
            comma = " and"

        if cid != -1:
            qstr = qstr + comma + " contest_id=%s" % str(cid)
            comma = " and"

        if hasUser:
            qstr += " and " + str(table) + ".user_id = public.user.id"

        if SelectDataQuery is None:
            sql_command = "SELECT * FROM %s;" % qstr
        else:
            sql_command = "SELECT %s FROM %s and admin_type != 'Super Admin';" % (SelectDataQuery, qstr)
            # sql_command = "SELECT submission.id, submission.create_time, submission.user_id, submission.username, " \
            #               "submission.code, submission.result, submission.info, submission.language, submission.shared, " \
            #               "submission.statistic_info, submission.ip, " \
            #               "submission.contest_id, submission.problem_id, submission.lecture_id," \
            #               "public.user.schoolssn FROM %s;" % qstr

        print(sql_command)

        data = pd.read_sql(sql_command, self.conn)

        return (data)

    def update_matches(self, id, jsondata):
        match_colname = 'plag_match'
        usql = "UPDATE "+self.sub_tablename+" SET "+match_colname+" = %s WHERE id = %s"
        self.cursor.execute(usql, (jsondata, id))
        self.conn.commit()

    def __del__(self):
        self.cursor.close()
        self.conn.close()