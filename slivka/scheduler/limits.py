import logging

logger = logging.getLogger('slivka.scheduler.scheduler')


class LimitsMeta(type):

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        if 'configurations' not in dct:
            raise RuntimeError('configurations are not listed')
        for conf_name in dct['configurations']:
            if 'limit_%s' % conf_name not in dct:
                raise RuntimeError('limit_%s missing' % conf_name)


class LimitsBase(metaclass=LimitsMeta):
    configurations = []

    def select_configuration(self, fields):
        try:
            self.setup(fields)
        except Exception:
            logger.exception('Failed to setup configuration check',
                             exc_info=True)
            return None
        for config in self.configurations:
            test = getattr(self, 'limit_%s' % config, None)
            try:
                if test(fields):
                    return config
            except Exception:
                logger.exception(
                    'Limit check for configuration %s raised an exception',
                    config, exc_info=True
                )
        else:
            return None

    def setup(self, values):
        pass
