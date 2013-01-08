from app import *
from tools.gushim import GUSHIM
# from models import *
# from flaskr import init_db

from optparse import OptionParser

parser = OptionParser()
parser.add_option("--force", dest="force", default=False, action="store_true", help="delete existing dbs")

(options, args) = parser.parse_args()

if not options.force:
	print "This script will delete the gushim and plans collection. To make sure this isn't running by mistake, run this with --force"
	exit()

# print "Deleting db.gushim and db.plans"
db.gushim.drop()
db.plans.drop()

db.gushim.create_index([('gush_id', 1)], unique=True)

for g in GUSHIM:
	db.gushim.insert({
		'gush_id'	: g,
		'html_hash' : '',
		'last_checked_at': ''
	})

db.plans.create_index([
	('number' ,1),
	('gush_id',1),
	('essence',1),
	('date'	  ,1)
	], unique = True)