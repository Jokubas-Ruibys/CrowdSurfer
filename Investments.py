from pymongo import MongoClient
from bs4 import BeautifulSoup
from pprint import pprint
import calendar
import time
import requests
import json

#Pull investment projects from CrowdCube website and put them into MongDB
def pullCrowdCubeInvestments( coll ):
	
	req = requests.get('https://www.crowdcube.com/investments')
	soup = BeautifulSoup(req.text, 'html.parser')
	
	#The website doesn't load all investment projects at once and implements paging. We store the link to the next page
	next_page = soup.find("div", class_="cc-paginate").get("data-nextcursor")
	
	while True:
		
		#for loop goes through each possible investment project in a given page
		for section in soup.find_all('section'):
			
			#Put everything in try/except block, in case we can't pull one investment project, maybe we can pull the others
			try:
				
				#Pull the information about investment project
				title = section.find("div", class_= "cc-card__content").h3.string
				short_summary = section.find("div", class_= "cc-card__content").p.string
				amount_raised = int(section.find("div", class_= "cc-card__stats").ul.li.b.string.replace("£", "").replace(",", ""))
				percentage_raised = int(section.find("div", class_="cc-card__stats").find("span").string.strip().replace("%",""))
		
				days_remaining = section.find("span", class_="cc-card__daysleft").string
				if days_remaining == "Last day":
					days_remaining = 1
				else:
					days_remaining = int(days_remaining.partition(' ')[0])
			
				link = section.find("a", class_="cc-card__link").get("href")
				
				#Put this information to the database
				coll.insert_one({
					"Title" : title,
					"Short Summary" : short_summary,
					"Amount Raised" : amount_raised,
					"Percentage Raised" : percentage_raised,
					"Days Remaining" : days_remaining,
					"Link" : link
				})
			except AttributeError:
				print ("Investment was not added to the database due to AttributeError")
			except ValueError:
				print ("Investment was not added to the database due to ValueError")
				
		#If this is the last page of projects, return
		if next_page == "":
			return
		
		#Load the next page of projects
		else:
			req = requests.get('https://www.crowdcube.com/investments?cursor=' + next_page)
			soup = BeautifulSoup(req.text, 'html.parser')
			next_page = soup.find("div", class_="cc-paginate").get("data-nextcursor")
			
			
	
#Pulls investment projects from KickStarter website and puts them to the database
def pullKickStarterInvestments( coll ):
	
	#The currency used in KickStarter is USD. We want to save all information in our database in GBP, so get live exchange rate
	currency = requests.get("http://api.fixer.io/latest?base=USD")
	currency = json.loads(currency.text)
	usdToGbp = currency["rates"]["GBP"]
	
	count = 0;
	pageNo = 0;
	
	while True:
		
		#KickStarter implements paging and does not give all investments at once, so we need to load page by page
		pageNo = pageNo+1
		
		#Pull .json file from KickStarter website, for projects in Art
		req = requests.get("https://www.kickstarter.com/discover/advanced.json?category_id=1&woe_id=0&sort=magic&page=" + str(pageNo))
		
		#Load .json data from KickStarter page
		data = json.loads(req.text)
		projects = data["projects"]

		#Looping through investment projects in json file and adding them to database
		for project in projects:
			
			#Put everything in try/except block, in case we can't pull one project, maybe we can pull others
			try:
				title = project["name"]
				short_summary = project["blurb"]
				amount_raised = int(float(project["usd_pledged"]) * usdToGbp)
				percentage_raised = int(project["pledged"]/project["goal"]*100)
				days_remaining = int((project["deadline"] - calendar.timegm(time.gmtime()))/86400)
				link = project["urls"]["web"]["project"]
	
				coll.insert_one({
					"Title" : title,
					"Short Summary" : short_summary,
					"Amount Raised" : amount_raised,
					"Percentage Raised" : percentage_raised,
					"Days Remaining" : days_remaining,
					"Link" : link
				})
		
				#Keeps track of the number of investments already in the database
				count = count +1
			    
				#If we already have 100 investments in the database, terminate
				if count >= 100:
					return
				
			except KeyError:
				print ("Investment was not added to the database due to KeyError")
			except ValueError:
				print ("Investment was not added to the database due to ValueError")
				
				

#Calculate Total Raised (Approach 1)
def totalRaised1( coll ):
	cursor = coll.find()
	totalAmount = 0
	for item in cursor:
		if (item["Days Remaining"] >= 10):
			totalAmount += item["Amount Raised"]
	return totalAmount


		
#Calculate Total Raised (Approach 2)
def totalRaised2( coll ):
	cursor = coll.aggregate(
    	[
			{"$match": {"Days Remaining": {"$gt": 9}}},
			{"$group": {"_id" : 0, "Total Raised": {"$sum": "$Amount Raised"}}}
		]
	)
	return cursor.next()["Total Raised"]



#Main function to be excecuted
def main():
	client = MongoClient()
	db = client.Investments

	#Creating a MongoDB Collection to store CrowdCube information
	db.CrowdCube.drop()
	collection1 = db.CrowdCube

	#Creating a MongoDB Collection to store KickStarter information
	db.KickStarter.drop()
	collection2 = db.KickStarter

	#Pulls investment information from CrowdCube and KickStarter websites
	pullCrowdCubeInvestments( collection1 )
	pullKickStarterInvestments( collection2 )

	#Calculates total amount raised for CrowdCube and Kickstarter, when there are at least 10 days left
	CrowdCubeTotalRaised = totalRaised2(collection1)
	KickStarterTotalRaised = totalRaised2(collection2)

	#Prints the amount raised for KickStarter and CrowdCube
	print (CrowdCubeTotalRaised)
	print (KickStarterTotalRaised)
	
	

if __name__ == "__main__":
	main()
