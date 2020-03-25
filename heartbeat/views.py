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
import logging
import psutil
#!/usr/bin/env python

logger = logging.getLogger("django.heartbeat")

class HeartBeatView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        print("test2")
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

        try: # 저지 서버의 마지막 heartbeat를 확인한다.
            servers = JudgeServer.objects.all()
            print(servers[0].last_heartbeat)
            if (str(now) - servers[0].last_heartbeat).seconds > 10:
                output_data['judge_server'] = False
        except:
            print("judge-server Not Exist")
            output_data['judge_server'] = False


        try:
            Permission.objects.get(id = 1) #django permission. Should be always available
            cache.set('test', 1)
            cache_get = cache.get('test')
            if cache_get != 1:
                raise ValueError

            request.session['test_value'] = 1
            request.session.save()

            assert request.session["test_value"] == 1

            extra_values = getattr(settings, "HEARTBEAT_OUTPUT", None)
            if extra_values:
                for k, v in extra_values.iteritems():
                    output_data[k] = v()
        except OperationalError:
            print("DB Error")
            output_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            res = 'failed'
            output_data['heartbeat'] = res
            output_data['postgres'] = False
            #return Response(output_data, status=output_status)
            return self.success(output_data)

        except ConnectionError:
            print("redis Error")
            output_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            res = 'failed'
            output_data['heartbeat'] = res
            output_data['redis'] = False
            #return Response(output_data, status=output_status)
            return self.success(output_data)

#        except Exception as e:
#            print(e)
#            logger.exception("Heartbeat Exception")
#            output_status = status.HTTP_500_INTERNAL_SERVER_ERROR
#            res = 'failed'

        output_data['heartbeat'] = res

        print(output_data)

        #return Response(output_data, status = output_status)
        return self.success(output_data)


class StaticHeartbeatView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        output_data = {}
        print("test")


        output_status = status.HTTP_200_OK
        output_data['heartbeat'] = 'ok'

        return Response(output_data, status = output_status)