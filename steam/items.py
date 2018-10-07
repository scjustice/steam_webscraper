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
    description = scrapy.Field()
    percent_pos = scrapy.Field()
    total_reviews = scrapy.Field()
    release_date = scrapy.Field()
    developer = scrapy.Field()
    publisher = scrapy.Field()
    early_access = scrapy.Field()

    def __str__(self):
#        return 'title = {}'.format(self['title'])
        return '''Title = {} : tags = {}
        % positive = {} Num of Reviews = {}
        Release Date = {}, Developer = {}, Publisher = {}
        Early Access = {}
        Description = {}
        '''.format(self['title'], str(self['tag_list']), self['percent_pos'], self['total_reviews'],
            self['release_date'], self['developer'], self['publisher'], str(self['early_access']),
            self['description'])

class SteamReviewItem(scrapy.Item):
    user = scrapy.Field()
    products_owned = scrapy.Field()
    num_reviews = scrapy.Field()
    recommend = scrapy.Field()
    review_text = scrapy.Field()
    time_played = scrapy.Field()
    num_helpful = scrapy.Field()
    num_funny = scrapy.Field()


