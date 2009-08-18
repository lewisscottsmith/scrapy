"""
This is a middleware to respect robots.txt policies. To active it you must
enable this middleware and enable the ROBOTSTXT_OBEY setting.

"""

import robotparser

from scrapy.xlib.pydispatch import dispatcher

from scrapy.core import signals
from scrapy.core.engine import scrapyengine
from scrapy.core.exceptions import NotConfigured, IgnoreRequest
from scrapy.http import Request
from scrapy.utils.httpobj import urlparse_cached
from scrapy.conf import settings

class RobotsTxtMiddleware(object):
    DOWNLOAD_PRIORITY = 1000

    def __init__(self):
        if not settings.getbool('ROBOTSTXT_OBEY'):
            raise NotConfigured

        self._parsers = {}
        self._spider_netlocs = {}
        self._useragents = {}
        self._pending = {}
        dispatcher.connect(self.domain_open, signals.domain_open)
        dispatcher.connect(self.domain_closed, signals.domain_closed)

    def process_request(self, request, spider):
        useragent = self._useragents[spider]
        rp = self.robot_parser(request.url, spider)
        if rp and not rp.can_fetch(useragent, request.url):
            raise IgnoreRequest("URL forbidden by robots.txt: %s" % request.url)

    def robot_parser(self, url, spider):
        netloc = url.netloc
        if netloc not in self._parsers:
            self._parsers[netloc] = None
            robotsurl = "%s://%s/robots.txt" % (url.scheme, url.netloc)
            robotsreq = Request(robotsurl, priority=self.DOWNLOAD_PRIORITY)
            dfd = scrapyengine.download(robotsreq, spider)
            dfd.addCallback(self._parse_robots)
            self._spider_netlocs[spider].add(netloc)
        return self._parsers[netloc]

    def _parse_robots(self, response):
        rp = robotparser.RobotFileParser(response.url)
        rp.parse(response.body.splitlines())
        self._parsers[urlparse_cached(response).netloc] = rp

    def domain_open(self, spider):
        self._spider_netlocs[spider] = set()
        self._useragents[spider] = getattr(spider, 'user_agent', None) \
            or settings['USER_AGENT']

    def domain_closed(self, domain, spider):
        for netloc in self._spider_netlocs[domain]:
            del self._parsers[netloc]
        del self._spider_netlocs[domain]
        del self._useragents[spider]
