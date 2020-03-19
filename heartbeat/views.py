from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger("django.heartbeat")

class HeartBeatView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        output_data = {}

        output_status = status.HTTP_200_OK
        res = 'ok'
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

        except Exception:
            logger.exception("Heartbeat Exception")
            output_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            res = 'failed'

        output_data['heartbeat'] = res

        return Response(output_data, status = output_status)


class StaticHeartbeatView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        output_data = {}

        output_status = status.HTTP_200_OK
        output_data['heartbeat'] = 'ok'

        return Response(output_data, status = output_status)