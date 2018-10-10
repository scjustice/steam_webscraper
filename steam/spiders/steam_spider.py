from scrapy import Spider, Request
from steam.items import SteamGameItem, SteamReviewItem
from scrapy_splash import SplashRequest

error_urls = []
lua_review_script = '''
function main(splash, args)
  splash:go(args.url)
  getTest = splash:jsfunc([[
    function() {
    return document.getElementsByClassName('apphub_NoMoreContent')[0].getAttribute('style')
    }
  ]])
  scrollScreen = splash:jsfunc([[
    function() {
        window.scrollBy(0, 2*window.innerHeight)
    }
  ]])
  while (getTest() == 'display: none') do
    scrollScreen()      
    splash:wait(1)
  end   
  return splash:html()
end'''

lua_detail_script = '''
function main(splash, args)
  splash.images_enabled = false
  assert(splash:go(args.url))
  assert(splash:wait(0.5))
  check_for_age = splash:runjs([[
    if (document.getElementById("ageYear") != null) {
      btn = document.getElementsByClassName("btnv6_blue_hoverfade btn_medium")
      document.getElementById("ageYear").value = 1982
      btn[0].click()
    }
    ]])
    splash:wait(2)
  return splash:html()
end
'''


class SteamSpider(Spider):
    name = 'steam_spider'
    allowed_urls = ['https://store.steampowered.com']
    start_urls = ['https://store.steampowered.com/tag/browse/#global_492']

    def parse(self, response):
        ''' Start by parsing the list of tags


        '''

        tag_list_rows = response.xpath('//div[@class="tag_browse_tag"]')
        tag_list = []
        for row in tag_list_rows:
            tag_id = row.xpath('./@data-tagid').extract_first()
            tag_list.append(tag_id)
        print('*' * 50)

        browse_by_tag_urls = [(x, ('https://store.steampowered.com/search/?' +
                                   'tags={}&category1=998&supportedlang=' +
                                   'english').format(x))
                              for x in tag_list]
#        print('Length of tag urls = {}'.format(len(browse_by_tag_urls)))

        for tag_url in browse_by_tag_urls[0:2]:
            print('Browsing {}'.format(tag_url[1]))
            print('=' * 50)

            yield Request(url=tag_url[1], meta={'tag_id': tag_url[0]},
                          callback=self.parse_tag_browse_list)
#           yield Request(url=url, callback=self.parse_tag_browse_list)
#           should go to a page to list out the browse pages

    def parse_tag_browse_list(self, response):

        tag_id = response.meta['tag_id']
        last_page = int(response.xpath('//div[@class="search_pagination_' +
                                       'right"]/a/text()')[-2].extract())

        genre_browse_url_list = [('https://store.steampowered.com/search/?' +
                                  'tags={}&category1=998&page={}&' +
                                  'supportedlang=english')
                                 .format(tag_id, x)
                                 for x in range(1, last_page+1)]

        for url in genre_browse_url_list[0:1]:
            print('Browsing {}'.format(url))
            yield Request(url=url, callback=self.parse_tag_browse_page)

    def parse_tag_browse_page(self, response):
        '''Browse an individual page that lists 25 games per page

        '''
        import re

        game_list = response.xpath('//div[@id="search_result_container"]' +
                                   '/div[2]/a')
        print('-' * 50)

        for game in game_list:
            detail_url = game.xpath('./@href').extract_first()
            game_id = re.search('app/(\d+)/', detail_url).group(1)
            title = game.xpath('.//span[@class="title"]/text()')\
                        .extract_first()

            price = game.xpath('.//div[@class="col search_price  ' +
                               'responsive_secondrow"]/text()')\
                        .extract_first()
            if price is None:
                print('Game is on sale')
                orig_price = game.xpath('.//div[@class="col search_price ' +
                                        'discounted responsive_secondrow"]' +
                                        '/span/strike/text()')\
                                 .extract_first().strip('$')
                price = game.xpath('.//div[@class="col search_price ' +
                                   'discounted responsive_secondrow"]/text()')\
                            .extract()[1].strip().strip('$')
                print('Title = {}, original price = {}, price = {}'
                      .format(title, orig_price, price))
                print('game id = {}, url = {}'.format(game_id, detail_url))

                yield SplashRequest(url=detail_url,
                                    args={'wait': 0.5, 'images': 0,
                                          'lua_source': lua_detail_script,
                                          'timeout': 90},
                                    endpoint='execute',
                                    callback=self.parse_game_detail,
                                    meta={'title': title, 'price': price,
                                          'orig_price': orig_price,
                                          'game_id': game_id})

            elif price.strip() == '':
                continue
            else:
                price = price.strip().strip('$')
                print('Title = {}, price = {}, game id = {}, url = {}'.format
                      (title, price, game_id, detail_url))
            print('*' * 50)
            yield SplashRequest(url=detail_url,
                                args={'wait': 0.5, 'images': 0, 'timeout': 90,
                                      'lua_source': lua_detail_script},
                                endpoint='execute',
                                callback=self.parse_game_detail,
                                meta={'title': title, 'price': price,
                                      'game_id': game_id})

    def parse_game_detail(self, response):
        '''Browse the individual entries for a game
        '''
        import re

        tag_list = list(map(lambda x: x.strip(), response.xpath(
            '//div[@class="glance_tags popular_tags"]/a/text()').extract()))
        description = response.xpath('//div[@class="game_description_snippet' +
                                     '"]/text()')\
                              .extract_first().lstrip().rstrip()
#       Handle games with no reviews
        test_for_no_reviews = response.xpath('//div[@class="summary column"]' +
                                             '/text()')\
                                      .extract_first().strip()\
                                      .find('No user') >= 0

        print('*' * 50)
        if test_for_no_reviews:
            print('No reviews')
            percent_pos = 'N/A'
            total_reviews = '0'
        else:
            review_summary = response.xpath('//span[@class="nonresponsive_' +
                                            'hidden responsive_reviewdesc"' +
                                            ']/text()')\
                                     .extract_first().strip()
#       Handle games with some reviews but not enough for percent_pos
            if review_summary.find('Need') >= 0:
                print('Not enough reviews for a % positive')
                percent_pos = 'N/A'
                total_reviews = re.search('(\d+) user', response.xpath(
                                          '//span[@class="game_review_' +
                                          'summary not_enough_reviews"]' +
                                          '/text()')
                                          .extract_first()).group(1)
            else:
#               Handle games with large number of reviews
                print('Enough reviews for % positive')
                total_reviews = response.xpath('//div[@class="summary ' +
                                               'column"]/span[@class=' +
                                               '"responsive_hidden"]/text()')\
                    .extract()[-1].strip().strip('()').replace(',', '')
                print('Total number of reviews = {}'.format(total_reviews))
                percent_pos = re.search('(\d+)%', response.xpath(
                                        '//span[@class="nonresponsive_hidden' +
                                        ' responsive_reviewdesc"]/text()')
                                        .extract_first()).group(1)
#        try:
#            percent_pos,total_reviews = re.search('(\d+)% of the (\d+,?\d+)', \
#                response.xpath('//div[@class="user_reviews_summary_row"]/@data-tooltip-text').extract_first()).group(1,2) 
        release_date = response.xpath('//div[@class="release_date"]/div[@class="date"]/text()').extract_first()
        developer = response.xpath('//div[@id="developers_list"]/a/text()').extract_first()        
        publisher = response.xpath('//div[@class="summary column"]/a/text()').extract_first()
        early_access = response.xpath('//div[@class="early_access_header"]') == []

        game_item = SteamGameItem()
        game_item['title'] = response.meta['title']
        game_item['game_id'] = response.meta['game_id']
        game_item['tag_list'] = tag_list
        game_item['price'] = response.meta['price']
        if 'orig_price' in response.meta.keys():
            game_item['orig_price'] = response.meta['orig_price']
        game_item['description'] = description
        game_item['percent_pos'] = percent_pos
        game_item['total_reviews'] = total_reviews
        game_item['release_date'] = release_date
        game_item['developer'] = developer
        game_item['publisher'] = publisher
        game_item['early_access'] = early_access

        print(game_item)

        yield game_item
#        review_url = ('https://steamcommunity.com/app/{}/reviews/' +
#                      '?browsefilter=toprated&snr=1_5_reviews_')\
#            .format(response.meta['game_id'])
#        print(review_url)
#        yield SplashRequest(url=review_url,
#                            args={'wait': 0.5, 'images': 0, 'timeout': 3600,
#                                  'lua_source': lua_review_script},
#                            endpoint='execute',
#                            callback=self.parse_game_review,
#                            meta={'title': response.meta['title']})


# Yield an Item that contains info for the game
# And then yield a request with the review url

    def parse_game_review(self, response):
        ''' Parse the reviews of a game after letting splash scroll through all
           of the pages so that all reviews are loaded
        '''
        import re

        print('*' * 50)
        print('Parsing the review for {}').format(response.meta['title'])
        print('*' * 50)

        review_pages = response.xpath('//div[starts-with(@id,"page")]' +
                                      '[not(@class="apphub_CardRow")]')

        for page in review_pages[0:1]:
            review_rows = page.xpath('.//div[@class="apphub_Card ' +
                                     'modalContentLink interactable"]')
            for review in review_rows[0:1]:
                found_helpful = review.xpath('.//div[@class="found_helpful"]' +
                                             '/text()')
                num_helpful = re.search('(.*) people', found_helpful[0]
                                        .extract()).group(1).strip()
                num_funny = re.search('(.*) people', found_helpful[1]
                                      .extract()).group(1).strip()
                recommend = review.xpath('.//div[@class="title"]/text()')\
                                  .extract_first() == 'Recommended'
                hours_played = re.search('(.*) hrs', review.xpath('.//div' +
                                         '[@class="hours"]/text()')
                                         .extract_first()).group(1)
                date_posted = review.xpath('.//div[@class="date_posted"]' +
                                           '/text()').extract_first()\
                                                     .replace('Posted: ', '')
                if ',' not in date_posted:
                    date_posted += ', 2018'
                review_list = review.xpath('.//div[@class="apphub_Card' +
                                           'TextContent"]/text()')\
                                    .extract()[1:]
                review_text = '\n'.join(map(lambda x: x.strip(), review_list))
                username = review.xpath('.//div[@class="apphub_CardContent' +
                                        'AuthorName offline ellipsis"]' +
                                        '/a/text()').extract_first()
                products_owned = re.search('(.*) products', review.xpath(
                                           './/div[@class="apphub_Card' +
                                           'ContentMoreLink ellipsis"]' +
                                           '/text()').extract_first())\
                                   .group(1)

                item = SteamReviewItem()
                item['title'] = response.meta['title']
                item['recommend'] = recommend
                item['hours_played'] = hours_played
                item['date_posted'] = date_posted
                item['review_text'] = review_text
                item['username'] = username
                item['products_owned'] = products_owned
                item['num_helpful'] = num_helpful
                item['num_funny'] = num_funny

                print(item)
