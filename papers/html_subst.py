# Makes substitutions in an HTML file by querying a relational database.
# Only string match queries are supported.
# The HTML syntax is:
#
# <query field1=value1 field2=value2 ...>
# ...HTML code using <entry>...
# </query>
#
# The code inside will be repeated for every entry matching the query.
# The <entry> tag is used to insert fields of the entry.  Every entry has
# a "text" field.  For example,
# <ul>
# <query city="New York" hair=blonde><li><entry text>
# </query></ul>
# makes an unnumbered list of the text of all entries whose "city" field 
# is "New York" and whose "hair" field is "blonde".
#
# The query may contain repeated fields.  This requires matching entries
# to have all the given values for that field (see below for multi-valued 
# fields).
#
# The database is also represented in HTML.  An entry is a block of
# text containing at least one non-white character.  The text is
# automatically trimmed of leading and trailing whitespace.
# Entries are delimited by <globalfield> or <field>.
# The special tag <globalfield field_name=value> 
# will define a field value that applies to all following entries,
# until either a new value is specified for that field with a new
# <globalfield> tag, or the field is deactivated via <globalfield
# field_name="">.  The special tag <field field_name=value> 
# defines a field value that applies only to the next entry.
# If field_name matches a globalfield, the local binding has precedence
# and the globalfield will continue to take effect on the next entry.
# Field value "" is the same as not specifying the field at all.
# See example_db.
#
# Both field tags allow multiple field_name=value specifications.
# If the same field_name is repeated, then the entry will have multiple
# values for that field.  The entry will satisfy a query for any subset 
# of these values.
#
# A bug is that special tags like !DOCTYPE don't get echoed.
# This is a problem with sgmllib.py.
#
# Written by Thomas P. Minka

from urllib.request import urlopen
import sgmllib
import sys
import string
from copy import copy

# modifies result to include the entries in dict
def merge(result, dict):
    for key in dict.keys():
        value = dict[key]
        if len(value) == 0:
            # an empty value will clear the field
            try:
                del result[key]
            except KeyError:
                # ignore it if they clear a nonexistent field
                pass
        else:
            result[key] = value

# Convert a list of (key, value) pairs into a multi-dictionary.
# A multi-dictionary stores multiple values for a key together in a
# sub-dictionary.
def list2dict(list):
    dict = {}
    for key, value in list:
        if key in dict:
            # Already have the key.
            try:
                # Extend the value dictionary.
                dict[key][value] = 1
            except TypeError:
                # Need to make one first.
                dict[key] = {dict[key]:1, value:1}
        else:
            dict[key] = value
    return dict

# Returns 1 if dict contains value or if not a dictionary, equal to value.
def contains(dict, value):
    try:
        return value in dict
    except AttributeError:
        return dict == value

# Parses SGML and echoes it back into self.text
class EchoParser(sgmllib.SGMLParser):
    def __init__(self):
        sgmllib.SGMLParser.__init__(self)
        self.text = ''

    def unknown_starttag(self, tag, attrs):
        # reconstruct and add to savetext
        tagtext = '<' + tag
        if attrs:
            for name, value in attrs:
                tagtext = tagtext + " " + name + '=' + '"' + value + '"'
        tagtext = tagtext + '>'
        self.text = self.text + tagtext

    def unknown_endtag(self, tag):      
        # reconstruct and add to savetext
        tagtext = '</' + tag + '>'
        self.text = self.text + tagtext

    # remove all entitydef conversions
    entitydefs = {}

    def unknown_entityref(self, ref):
        text = '&' + ref + ';'
        self.text = self.text + text

    def unknown_charref(self, ref):
        text = '&#' + ref + ';'
        self.text = self.text + text

    def handle_data(self, text):
        self.text = self.text + text

    def handle_comment(self, text):
        text = "<!-- " + text + "-->"
        self.text = self.text + text

class Database(EchoParser):
    # table is a set of entries
    # an entry is a hash table of fields as well as a special 'text' key
    def __init__(self):
        EchoParser.__init__(self)
        # the current set of attributes
        self.local_attrs = {}
        self.global_attrs = {}
        # the table of entries
        self.table = []

    def close(self):
        EchoParser.close(self)
        self.complete_entry()

    # complete the current entry and enter it in the table
    def complete_entry(self):
        # trim the text
        self.text = self.text.strip()
        # has there been any text?
        if len(self.text) == 0:
            return
        # make a new entry for the text just ended
        entry = copy(self.global_attrs)
        # local_attrs override global_attrs
        merge(entry, self.local_attrs)
        # local_attrs no longer apply
        self.local_attrs = {}
        entry['text'] = self.text
        self.text = ''
        self.table.append(entry)

    # The parser will automatically call this when it reads '<field ...>'
    def start_field(self, attrs):
        self.complete_entry()
        # merge new attrs with old ones 
        merge(self.local_attrs, list2dict(attrs))

    # The parser will automatically call this when it reads '<globalfield ...>'
    def start_globalfield(self, attrs):
        self.complete_entry()
        # merge new attrs with old ones 
        merge(self.global_attrs, list2dict(attrs))

    # returns a list of entries which match the attribute list
    def query(self, attrs):
        result = []
        for entry in self.table:
            match = 1
            for key, value in attrs:
                if value == '':
                    if key in entry:
                        match = 0
                        break
                else:
                    if key not in entry or not contains(entry[key], value):
                        match = 0
                    break
            if match:
                result.append(entry)
        return result

class HTMLSubst(EchoParser):
    # table is a set of entries
    # an entry is a hash table of fields as well as a special 'text' key
    def __init__(self, db):
        EchoParser.__init__(self)
        self.db = db
        self.table = None

    def flush(self):
        sys.stdout.write(self.text)
        self.text = ''

    def close(self):
        EchoParser.close(self)
        self.flush()

    # The parser will automatically call this when it reads '<query ...>'
    def start_query(self, attrs):
        self.flush()
        self.table = self.db.query(attrs)
        self.template = []

    # The parser will automatically call this when it reads '</query>'
    def end_query(self):
        if self.table == None:
            raise "query ended before it was begun"
        # finish the template
        self.template.append(self.text)
        # loop the table and substitute text for each entry
        for entry in self.table:
            sys.stdout.write(self.substitute(self.template, entry))
        self.text = ''

    # The parser will automatically call this when it reads '<entry ...>'
    def do_entry(self, attrs):
        if len(attrs) != 1:
            raise "entry tag must have exactly one attribute"
        self.template.append(self.text)
        self.template.append(attrs[0][0])
        self.text = ''

    def substitute(self, template, entry):
        result = ''
        istext = 1
        # loop the template
        for s in template:
            if istext:
                result = result + s
            else:
                try:
                    result = result + str(entry[s])
                except KeyError as msg:
                    pass
                    #sys.stderr.write("\nWarning: This entry has no field `"+str(msg)+"':\n")
                    #sys.stderr.write(entry["text"]+"\n\n")
            istext = not istext
        return result

def read_db(url):
    # open the database
    try:
        f = open(url)
    except IOError as msg:
        print('***', url, ':', msg)
        return 0

    # parse the database
    db = Database()
    db.feed(f.read())
    db.close()
    f.close()

    return db

def do(url, db):
    # open the url
    try:
        f = open(url)
    except IOError as msg:
        print('***', url, ':', msg)
        return 0
    
    # parse and substitute
    parser = HTMLSubst(db)
    print("<!-- THIS IS AN AUTOMATICALLY GENERATED FILE.  DO NOT EDIT THIS FILE! -->")
    parser.feed(f.read())
    parser.close()
    f.close()

if len(sys.argv) < 3:
    print("usage: python html_subst.py url db_url")
    sys.exit(1)
db = read_db(sys.argv[2])
do(sys.argv[1], db)
