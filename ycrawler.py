import asyncio
import cssselect
import aiohttp
import os
import time
import logging
import async_timeout
from optparse import OptionParser
from lxml import html as lhtml
from io import StringIO
from random import randint
from collections import deque


URL = "https://news.ycombinator.com/"
LAST_NEWS_ID = deque(['0000000'], 1)


# return DOM (document object model)
def get_dom(document):
    return lhtml.document_fromstring(document)


def get_dom_elements(dom, css, element):
    items = dom.cssselect(css)
    for item in items:
        yield item.get(element)


# make directory for news save  
def make_dir(id):
    directory = time.strftime("%Y%m%d-%H%M%S-") + id
    new_dir = os.path.join(os.path.abspath(os.getcwd()), directory)
    try:
        os.mkdir(new_dir)
    except Exception as e:
        logging.info(e)
    else:
        return new_dir
    

# return deque with 30 news id
def make_deque(doc):
    dom = get_dom(doc)
    return deque(get_dom_elements(dom, '.athing', 'id'), 30)


async def get_url(session, url):
    logging.info(url)
    async with session.get(url) as response:
        return response.status, await response.text()


async def fetch(url):
    async with aiohttp.ClientSession() as session:
        try:
            status, html = await get_url(session, url)
        except Exception as e:
            logging.info(e)
            return 500, e
        else:
            return status, html


async def get_news(main_page):
    news_id_list = make_deque(main_page) # deque with 30 news id
    save_id = news_id_list[0] # save last news id

    # start from upper news and compare with saved upper news
    for id in news_id_list:
        logging.info(id + " " + LAST_NEWS_ID[0])
        if id == LAST_NEWS_ID[0]:
            break # already saved
        else:
            await save_news(id, main_page)

    LAST_NEWS_ID.append(save_id) # it is id of last saved news'
    

async def download_coroutine(session, url, path):
    logging.info(url)
    try:
        with async_timeout.timeout(10):
            async with session.get(url) as response:
                with open(path, 'wb') as index:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        index.write(chunk)
    except asyncio.TimeoutError:
        logging.info('timeout error %s' % url)
    except Exception as e:
        logging.info(e)
    else:
        return await response.release()


async def save_news(id, main_page):
    new_dir = make_dir(id)
    if not new_dir:
        return
    
    # download news
    css = 'tr#' + id + '.athing td.title a.storylink'
    news_url = get_dom_elements(get_dom(main_page), css, 'href')
    
    async with aiohttp.ClientSession() as session:
        for url in news_url:
            filename = 'index' + str(randint(10000, 99999)) + '.html'
            path = os.path.join(new_dir, filename)
            await download_coroutine(session, url, path)
    
    # doownload refs in comments
    comments_ref = URL + 'item?id=' + id
    status, comments_page = await fetch(comments_ref)
    if status == 200:
        css = '.default .comment .c00 a[rel="nofollow"]'
        comments_link = get_dom_elements(get_dom(comments_page), css, 'href')
    
    async with aiohttp.ClientSession() as session:
        for url in comments_link:
            filename = 'comments' + str(randint(10000, 99999)) + '.html'
            path = os.path.join(new_dir, filename)
            await download_coroutine(session, url, path)


async def get_main_page():
    while True:
        status, main_page = await fetch(URL)
        if status == 200:
            await get_news(main_page)
        await asyncio.sleep(30)

def main():
    op = OptionParser()
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_main_page())
    loop.close()

main()
