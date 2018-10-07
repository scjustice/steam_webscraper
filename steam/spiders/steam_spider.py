from scrapy import Spider, Request
from steam.items import SteamGameItem
from scrapy_splash import SplashRequest

lua_script_reviews = '''
function main(splash, args)
  splash.images_enabled = false
  assert(splash:go(args.url))
  assert(splash:wait(0.5))
  local btn = splash:select('div[id=age_gate_btn_continue]')
  if btn ~= nil then
    btn:click()
  end
  end_page = splash:select('div[id=NoMoreContent][style="opacity: 1;"]')
  count = 0
  --ypos = 1000
  local scroll_down = splash:jsfunc("window.scrollBy")
  local get_body_height = splash:jsfunc(
        "function() {return document.body.scrollHeight;}"
    )

  while (end_page == nil) do
    --splash.scroll_position = {y=ypos}
    scroll_down(0, get_body_height())
    splash:wait(1)
    end_page = splash:select('div[id=NoMoreContent][style="opacity: 1;"]')
    count = count + 1
  end
  return splash:html()
end'''

lua_script_detail = '''
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
#            tag_label = row.xpath('./text()').extract_first()
            tag_list.append(tag_id)
        print('*' * 50)

        browse_by_tag_urls = [(x, ('https://store.steampowered.com/search/?' +
                                  'tags={}&category1=998&supportedlang=' +
                                  'english').format(x))
                              for x in tag_list]
        print('Length of tag urls = {}'.format(len(browse_by_tag_urls)))

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

        genre_browse_url_list = ['https://store.steampowered.com/search/?' +
                                 'tags={}&category1=998&page={}'
                                 .format(tag_id, x)
                                 for x in range(1, last_page+1)]

        for url in genre_browse_url_list[0:1]:
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
#                print("Title = {}".format(title))
                orig_price = game.xpath('.//div[@class="col search_price ' +
                                        'discounted responsive_secondrow"]' +
                                        '/span/strike/text()')\
                                 .extract_first().strip('$')
#                print("Original price = {}".format(orig_price))
                price = game.xpath('.//div[@class="col search_price ' +
                                   'discounted responsive_secondrow"]/text()')\
                            .extract()[1].strip().strip('$')
#                print("Price = {}".format(price))
#                print("Url = {}".format(detail_url))
                print('Title = {}, original price = {}, price = {}'
                      .format(title, orig_price, price))
                print('game id = {}, url = {}'.format(game_id, detail_url))

                yield SplashRequest(url=detail_url,
                                    args={'wait': 0.5, 'image': 0,
                                          'lua_source': lua_script_detail},
                                    endpoint='execute',
                                    callback=self.parse_game_detail,
                                    meta={'title': title, 'price': price,
                                          'orig_price': orig_price})

            elif price.strip() == '':
                continue
            else:
                price = price.strip().strip('$')
                print('Title = {}, price = {}, game id = {}, url = {}'.format
                      (title, price, game_id, detail_url))
            print('*' * 50)
            yield SplashRequest(url=detail_url,
                                args={'wait': 0.5, 'image': 0,
                                      'lua_source': lua_script_detail},
                                endpoint='execute',
                                callback=self.parse_game_detail,
                                meta={'title': title, 'price': price})

    def parse_game_detail(self, response):
        '''Browse the individual entries for a game
        '''
        import re

        print('response = {}'.format(response))
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
#        except AttributeError:
#            percent_pos = 'N/A'
#            total_reviews = 0
        release_date = response.xpath('//div[@class="release_date"]/div[@class="date"]/text()').extract_first()
        developer = response.xpath('//div[@id="developers_list"]/a/text()').extract_first()        
        publisher = response.xpath('//div[@class="summary column"]/a/text()').extract_first()
        early_access = response.xpath('//div[@class="early_access_header"]') == []

        game_item = SteamGameItem()
        game_item['title'] = response.meta['title']
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

#        yield game_item
#        review_url_list =

#   Yield an Item that contains info for the game then yield a url list of reviews



        


