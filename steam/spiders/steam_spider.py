from scrapy import Spider, Request
from steam.items import SteamGameItem, SteamReviewItem
from scrapy_splash import SplashRequest

lua_review_script = '''
function main(splash, args)
  splash:go(args.url)
  getTest = splash:jsfunc([[
    function() {
    ret_val = document.getElementsByClassName('apphub_NoMoreContent')
    return ret_val[0].getAttribute('style')
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
  assert(splash:go(args.url))
  assert(splash:wait(0.5))
  splash.images_enabled = false
  check_for_age = splash:runjs([[
    if (document.getElementById("ageYear") != null) {
      btn = document.getElementsByClassName("btnv6_blue_hoverfade btn_medium")
      document.getElementById("ageYear").value = 1982
      btn[0].click()
    }
    ]])
    splash:wait(3)
  return splash:html()
end
'''


class SteamSpider(Spider):
    ''' Class statement for the steam spider that is crawls the steam website.
    '''

    name = 'steam_spider'
    allowed_urls = ['https://store.steampowered.com']
    start_urls = ['https://store.steampowered.com/search/?category1=998' +
                  '&supportedlang=english']
    timeout_urls = 'timeout_urls.list'
    cur_tag_index_pair = 0

    def parse(self, response):
        # Start by parsing the initial search page.
        # Find the number for the last page of the games
        last_page = int(response.xpath('//div[@class="search_pagination_' +
                                       'right"]/a/text()')[-2].extract())
        # Use a list comprehension to generate all of the pages that will
        # need to be scraped.
        browse_url_list = [('https://store.steampowered.com/search/?' +
                            'sort_by=Released_DESC&category1=998&page={}&' +
                            'supportedlang=english').format(x)
                           for x in range(1, last_page+1)]
        # Yield a request for each page that contains a list of games
        for url in browse_url_list:
            yield Request(url=url, callback=self.parse_browse_page)

    def parse_browse_page(self, response):
        '''Browse an individual page that lists 25 games per page.

            This page contains the title, price, sale price if on sale,
            game_id, and url to the page that contains detail information.
        '''

        import re

        game_list = response.xpath('//div[@id="search_result_container"]' +
                                   '/div[2]/a')
        for game in game_list:
            # meta variable that will be passed forward to detail page
            meta = {}
            detail_url = game.xpath('./@href').extract_first()
            if detail_url.find('/sub/') > 0:
                # Skip entries that point to bundles since not tracking them.
                continue
            game_id = re.search('app/(\d+)/', detail_url).group(1)
            title = game.xpath('.//span[@class="title"]/text()')\
                        .extract_first()

            price = game.xpath('.//div[@class="col search_price  ' +
                               'responsive_secondrow"]/text()')\
                        .extract_first()
            meta = {'title': title, 'game_id': game_id}
            # if the price entry is empty that means game is on sale
            if price is None:
                # Parse the original price as well as the new sale price
                orig_price = game.xpath('.//div[@class="col search_price ' +
                                        'discounted responsive_secondrow"]' +
                                        '/span/strike/text()')\
                                 .extract_first().strip('$')
                price = game.xpath('.//div[@class="col search_price ' +
                                   'discounted responsive_secondrow"]/text()')\
                            .extract()[1].strip().strip('$')
                meta['price'] = price
                meta['orig_price'] = orig_price
            elif price.strip() == '':
                # Skip games that are not yet available for purchase
                continue
            else:
                ''' Remove the dollar sign from price, but keep a string to
                    but keep price as a string since want denote free to
                    play games. '''
                price = price.strip().strip('$')
                meta['price'] = price
                # Save original price as NaN for games that are not on sale.
                meta['orig_price'] = float('nan')
            # Yield a request that leads to the detail page for each game.
            # Also pass the meta variable containing price, title, and game_id.
            yield Request(url=detail_url, callback=self.parse_game_detail,
                          meta=meta)

    def parse_game_detail(self, response):
        '''Scrap the entries for an individual game.  '''
        import re

        # Check that the url for the reponse isn't an age check page
        if (response.url.find('agecheck') > 0):
            print('Age input needed for {}'.format(response.url))
            ''' If age check is required for the game, then forward request
                through scrapy-splash. Utilize the lua_detail_script already
                defined.

                Run splash with images = 0 to turn off image and reduce
                rendering time.
                Increase timeout to 90 seconds since some pages took longer
                to load.
                Endpoint = execute sets renderer to load the code defined in
                lua_source to run before passing on the request
                '''

            return SplashRequest(url=response.url,
                                 args={'wait': 0.5, 'images': 0, 'timeout': 90,
                                       'lua_source': lua_detail_script},
                                 endpoint='execute',
                                 callback=self.parse_game_detail,
                                 meta=response.meta)

        release_date = response.xpath('//div[@class="release_date"]/div' +
                                      '[@class="date"]/text()').extract_first()

        prerelease_test = response.xpath('//div[@class="game_area_comingsoon' +
                                         'game_area_bubble"]') != []
        # Skip games without release date or only available for prepurchase.
        if release_date == '' or prerelease_test:
            return

        tag_list = list(map(lambda x: x.strip(), response.xpath(
            '//div[@class="glance_tags popular_tags"]/a/text()').extract()))
        description = response.xpath('//div[@class="game_description_snippet' +
                                     '"]/text()')\
                              .extract_first().lstrip().rstrip()
        test_for_no_reviews = response.xpath('//div[@class="summary column"]' +
                                             '/text()')\
                                      .extract_first().strip()\
                                      .find('No user') >= 0

        # Handle games with no reviews
        if test_for_no_reviews:
            percent_pos = 'N/A'
            total_reviews = '0'
        else:
            review_summary = response.xpath('//span[@class="nonresponsive_' +
                                            'hidden responsive_reviewdesc"' +
                                            ']/text()')\
                                     .extract_first().strip()
            # Handle games with reviews but not enough for percent positive.
            if review_summary.find('Need') >= 0:
                percent_pos = 'N/A'
                total_reviews = re.search('(\d+) user', response.xpath(
                                          '//span[@class="game_review_' +
                                          'summary not_enough_reviews"]' +
                                          '/text()')
                                          .extract_first()).group(1)
            # Handle games with large number of reviews
            else:
                total_reviews = response.xpath('//div[@class="summary ' +
                                               'column"]/span[@class=' +
                                               '"responsive_hidden"]/text()')\
                    .extract()[-1].strip().strip('()').replace(',', '')
                percent_pos = re.search('(\d+)%', response.xpath(
                                        '//span[@class="nonresponsive_hidden' +
                                        ' responsive_reviewdesc"]/text()')
                                        .extract_first()).group(1)
        developer = response.xpath('//div[@id="developers_list"]/a/text()')\
                            .extract_first()
        publisher = response.xpath('//div[@class="summary column"]/a/text()')\
                            .extract_first()
        # Set a boolean for games under the early access program.
        early_access = response.xpath('//div[@class="early_access_header"' +
                                      ']') != []

        # Create a new game item and store the scraped data from current game.
        game_item = SteamGameItem()
        game_item['title'] = response.meta['title']
        game_item['game_id'] = response.meta['game_id']
        game_item['tag_list'] = tag_list
        game_item['price'] = response.meta['price']
        game_item['orig_price'] = response.meta['orig_price']
        game_item['description'] = description
        game_item['percent_pos'] = percent_pos
        game_item['total_reviews'] = total_reviews
        game_item['release_date'] = release_date
        game_item['developer'] = developer if developer is not None else 'N/A'
        game_item['publisher'] = publisher if publisher is not None else 'N/A'
        game_item['early_access'] = early_access

        return game_item

    def parse_game_review(self, response):
        ''' Parse the reviews of a game after letting splash scroll through all
            of the pages so that all reviews are loaded.

            This function is not used by the scraper because reviews are
            not saved alongside the game data.

        '''
        import re

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
                # Add the year to reviews that were made this year
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

                # Create a review item to hold the scraped data from reviews.
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
