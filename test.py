import urllib.request

url = 'https://www.globes.co.il/portal/instrument.aspx?instrumentid=773&mode=reports'

# response = urllib.request.urlopen('https://www.bizportal.co.il/capitalmarket/quote/reports/1087022')
response = urllib.request.urlopen(url)
html = response.read()

# from requests_html import HTMLSession

# session = HTMLSession()
# html = session.get(url)

from bs4 import BeautifulSoup
import time
from selenium import webdriver
import pandas as pd

driver = webdriver.Chrome(executable_path = 'C:/Program Files (x86)/Google/Chrome/Application/chromedriver.exe')
'''
driver.get(url)
driver.execute_script("javascript:showYearlyReport()")
time.sleep(2)
result = driver.find_element_by_id('divMainReportData1')

f = open("test.txt", "wb")
f.write(result.text.encode("utf-8"))
f.close()

net_profit = result.find_element_by_xpath('/table')


print("result: %s" % result)

print("net profit count: %s" % len(net_profit))

for value in net_profit:
  print("net profit: %s" % value.get_attribute("text"))

'''

driver.get("https://www.bizportal.co.il/capitalmarket/quote/reports/770016")
time.sleep(2)

element = driver.find_element_by_css_selector("li[aria-controls='profit-and-loss-report-tabstrip-2']")
element.click()
time.sleep(2)

# JavascriptExecutor executor = (JavascriptExecutor)driver;
# executor.executeScript("arguments[0].click();", element);

result = driver.find_element_by_id('profit-and-loss-report-tabstrip')

# <li class="k-item k-state-default k-first k-tab-on-top k-state-active" role="tab" aria-controls="profit-and-loss-report-tabstrip-1" style="" aria-selected="true" id="profit-and-loss-report-tabstrip_ts_active"><span class="k-loading k-complete k-progress" style=""></span><span unselectable="on" class="k-link">רבעוניים</span></li>

f = open("test1.txt", "wb")
f.write(result.text.encode("utf-8"))
# f.write(result.get_attribute('innerHTML').encode("utf-8"))
f.close()

# driver.quit()





