from scrapy import Spider, Request
from steam.items import SteamItem

class SteamSpider(Spider):
    name = 'steam_spider'
    allowed_urls = ['https://store.steampowered.com']
    start_urls = ['https://store.steampowered.com/tag/browse/#global_492']


    def parse(self, response):
        ''' Start by parsing the list of tags


        '''

        tag_list_rows = response.xpath('//div[@class="tag_browse_tag"]')
        #tag_list_rows = response.xpath('//div[@class="tag_browse_tags"]/div[@class="browse-tags"')
        tag_list = []
        for row in tag_list_rows:
            tag_id = row.xpath('./@data-tagid').extract_first()
            tag_label = row.xpath('./text()').extract_first()
            tag_list.append(tag_id)
        print('*' * 50)

        browse_by_tag_urls = [(x,'https://store.steampowered.com/search/?sort_by=Released_DESC&tags={}&category1=998'.format(x)) for x in tag_list]
        print('Length of tag urls = {}'.format(len(browse_by_tag_urls)))
        
        for tag_url in browse_by_tag_urls[0:2]:
            print('Browsing {}'.format(tag_url[1]))
            print('=' * 50)
            
            yield Request(url=tag_url[1], meta={'tag_id':tag_url[0]}, callback=self.parse_tag_browse_list)
            #yield Request(url=url, callback=self.parse_tag_browse_list)  #should go to a page to list out the browse pages
        
    def parse_tag_browse_list(self, response):

        tag_id = response.meta['tag_id']
        last_page = int(response.xpath('//div[@class="search_pagination_right"]/a/text()')[-2].extract())

        genre_browse_url_list = ['https://store.steampowered.com/search/?sort_by=Released_DESC&tags={}&category1=998@page={}'.format(tag_id, x) for x in range(1, last_page+1)] 

        for url in genre_browse_url_list[0:5]:
            yield Request(url=url, callback=self.parse_tag_browse_page)



    def parse_tag_browse_page(self, response):
        '''Browse an individual page that lists 25 games per page

        '''

        game_list = response.xpath('//div[@id="search_result_container"]/div[2]/a')

        for game in game_list:
            detail_url = game.xpath('./@href').extract_first()
            title = game.xpath('.//span[@class="title"]/text()').extract_first()
            
            price = game.xpath('.//div[@class="col search_price  responsive_secondrow"]/text()').extract_first()
            if price == None:
                orig_price = game.xpath('.//div[@class="col search_price discounted responsive_secondrow"]/span/strike/text()').extract_first().strip('$')
                price = game.xpath('.//div[@class="col search_price discounted responsive_secondrow"]/text()').extract()[1].strip().strip('$')
                print('Title = {}, original price = {}, price = {}, url = {}'.format(title, orig_price, price, detail_url))
            elif price.strip() == '':
                continue
            else:
                price = price.strip().strip('$')
                print('Title = {}, price = {}, url = {}'.format(title, price, detail_url))
            print('*' * 50)

#                yield Request(url=detail_url, meta={'title'=title, 'price'=game_price}, callback=self.parse_game_detail)
                



        
