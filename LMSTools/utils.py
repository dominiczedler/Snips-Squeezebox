try:
    import urllib.parse
    urlmodule = urllib.parse
except ImportError:
    import urllib
    urlmodule = urllib


class LMSUtils(object):
    @staticmethod
    def quote(text):
        return urlmodule.quote(text)

    @staticmethod
    def unquote(text):
        return urlmodule.unquote(text)
