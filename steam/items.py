# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class SteamGameItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    tag_list = scrapy.Field()
    title = scrapy.Field()
    game_id = scrapy.Field()
    price = scrapy.Field()
    orig_price = scrapy.Field()
    description = scrapy.Field()
    percent_pos = scrapy.Field()
    total_reviews = scrapy.Field()
    release_date = scrapy.Field()
    developer = scrapy.Field()
    publisher = scrapy.Field()
    early_access = scrapy.Field()

    def __str__(self):
#       Need to handle price and original price
        ret_val = '''Title = {} : game_id = {} : tags = {}
        % positive = {} Num of Reviews = {}
        '''.format(self['title'], self['game_id'], str(self['tag_list']),
                   self['percent_pos'], self['total_reviews'])
        if ('orig_price' in self.keys()):
            ret_val += 'Original Price = {} Sale price = {}'\
                    .format(self['orig_price'], self['price'])
        else:
            ret_val += 'Price = {}'.format(self['price'])
        ret_val += '''
        Release Date = {}, Developer = {}, Publisher = {}
        Early Access = {}
        Description = {}
        '''.format(self['release_date'], self['developer'], self['publisher'],
                   str(self['early_access']), self['description'])

        return ret_val


class SteamReviewItem(scrapy.Item):
    title = scrapy.Field()
    recommend = scrapy.Field()
    hours_played = scrapy.Field()
    date_posted = scrapy.Field()
    review_text = scrapy.Field()
    username = scrapy.Field()
    products_owned = scrapy.Field()
    num_helpful = scrapy.Field()
    num_funny = scrapy.Field()

    def __str__(self):
        review_sum = ' '.join(self['review_text'].split()[0:10])
        ret_val = '''
        Title = {}
        Recommend = {}, Hours played = {}, Date posted = {}
        Review = {}
        Username = {}, Products owned = {}
        Number found helpful = {}, Number found funny = {}'''\
        .format(self['title'], str(self['recommennd']),
                self['hours_played'], self['date_posted'], review_sum,
                self['username'], self['products_owned'], self['num_helpful'],
                self['num_funny'])

        return ret_val
