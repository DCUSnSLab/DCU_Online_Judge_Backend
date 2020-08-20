import hashlib
from options.options import SysOptions

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.conf import settings
from conf.models import JudgeServer
from django.db.utils import OperationalError
from redis.exceptions import ConnectionError
from utils.api import APIView

from datetime import datetime, timedelta
import time
import logging
import psutil
#!/usr/bin/env python

logger = logging.getLogger("django.heartbeat")

class HeartBeatView(APIView):

    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        output_data = {}

        output_status = status.HTTP_200_OK
        res = 'ok'

        # gives a single float value
        cpu = psutil.cpu_percent()
        print('cpu:',cpu)
        # gives an object with many fields
        print('memory:',psutil.virtual_memory())
        # you can convert that object to a dictionary
        #dict(psutil.virtual_memory()._asdict())

        output_data['cpu_percent'] = str(cpu)
        output_data['memory'] = str(psutil.virtual_memory().percent)
        output_data['postgres'] = True
        output_data['redis'] = True
        output_data['judge_server'] = True

        now = datetime.now()
        output_data['current_time'] = str(now)

        judgetime = time.time()
        try: # 저지 서버의 마지막 heartbeat를 확인한다.
            servers = JudgeServer.objects.all()
            print("last_heartbeat",servers[0].last_heartbeat) # 저지 서버는 현재 1개만 가동중이므로 0번째 쿼리셋의 값을 가져온다.
            print("now", now)
            dt = servers[0].last_heartbeat.replace(tzinfo=None) # UTC datetime 포맷에서 tz값(+00:00)을 제거한다
            sub = now - dt
            if sub.seconds > 10:
                print("judge-server no response")
                output_data['judge_server'] = False
        except:
            print("judge-server Not Exist")
            output_data['judge_server'] = False

        judgetime = time.time() - judgetime
        print("저지 서버 연결 유무 확인", judgetime)
        output_data['judgetime'] = str(judgetime)

        postgrestime = time.time()
        try:
            get(id = 1) #django permission. Should be always available
            # cache.set('test', 1)
            # cache_get = cache.get('test')
            # if cache_get != 1:
            #     raise ValueError

            # request.session['test_value'] = 1
            # request.session.save()

            # assert request.session["test_value"] == 1

            # extra_values = getattr(settings, "HEARTBEAT_OUTPUT", None)
            # if extra_values:
            #     for k, v in extra_values.iteritems():
            #         output_data[k] = v()
        except OperationalError:
            print("postgres Error")
            output_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            res = 'failed'
            output_data['heartbeat'] = res
            output_data['postgres'] = False
            #return Response(output_data, status=output_status)

        postgrestime = time.time() - postgrestime
        print("데이터베이스 서버 연결 유무 확인", postgrestime)
        output_data['postgrestime'] = str(postgrestime)

        redistime = time.time()
        try:
            get(id = 1) #django permission. Should be always available
        except ConnectionError:
            print("redis Error")
            output_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            res = 'failed'
            output_data['heartbeat'] = res
            output_data['redis'] = False
            #return Response(output_data, status=output_status)

        redistime = time.time() - redistime
        print("redis 서버 연결 유무 확인", redistime)
        output_data['redistime'] = str(redistime)

        output_data['heartbeat'] = res

        print(output_data)

        return self.success(output_data)


class StaticHeartbeatView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        output_data = {}
        print("test")


        output_status = status.HTTP_200_OK
        output_data['heartbeat'] = 'ok'

        return Response(output_data, status = output_status)