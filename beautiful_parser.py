import bs4


def is_comment(element):
    return isinstance(element, bs4.Comment)


def find_by_class(soup, name, class_name):
    return soup.find(name, {'class': class_name})


def find_all_by_class(soup, name, class_name):
    return soup.find_all(name, {'class': class_name})


class BeautifulParser(bs4.BeautifulSoup):
    def __init__(self, obj):
        bs4.BeautifulSoup.__init__(self, obj, 'lxml')

    def find_by_class(self, name, class_name):
        return find_by_class(self, name, class_name)

    def find_all_by_class(self, name, class_name):
        return find_all_by_class(self, name, class_name)
