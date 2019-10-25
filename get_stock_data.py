import numpy
import sys
import codecs
import re
import statistics
import locale
import time
import argparse
import png
from selenium import webdriver
from selenium.webdriver.common.by import By

class Stock():

  def __init__(self,
               id: int) -> None:
    self._data = {}
    self._data['id'] = id

  def as_str(self):
    rv = ""
    for key in sorted(self._data.keys()):
      rv += "  %s = %s\n" % (key, self._data[key])

    return rv

  def load_from_str(self, data_str: str):
    for line in data_str.split('\n'):
      if line:
        line = line.strip()
        # print(">%s<" % line[0:6])
        (key,value) = line.split(" = ")
        self._data[key] = value
    return self

  def skip(self) -> bool:
    if '+skip' in self._data.keys():
      return self._data['+skip']
    else:
      return False

  # sphinx

  @staticmethod
  def get_stock_list_header() -> str:
    rv = ""
    rv += "  *  - Name\n"
    rv += "     - Id\n"
    rv += "     - Score\n"
    rv += "     - Market capital\n"
    rv += "     - Price\n"
    rv += "     - P/E\n"
    rv += "     - CFM\n"
    rv += "     - Op. profit to sales\n"
    rv += "     - Net profit to sales\n"
    rv += "     - Dividendxxx\n"
    rv += "     - Div. graph\n"
    rv += "     - Return\n"
    rv += "     - Return graph\n"
    rv += "     - Earnings\n"
    rv += "     - Earnings graph\n"
    rv += "     - Op. profit\n"
    rv += "     - Op. profit graph\n"
    return rv

  def get_stock_list_row(self) -> str:
    rv = ""
    rv += "  *  - `%s <%s%d>`_\n" % (self.get_name(), "https://www.bizportal.co.il/capitalmarket/quote/reports/", self.get_id())
  
    rv += "     - %s" % self.get_id()
    if self.skip(): rv += "*" 
    rv += "\n"

    rv += "     - %.1f\n" % self.get_score()
    rv += "     - %d\n" % self.get_market_capital()
    rv += "     - %.2f\n" % self.get_price()

    pe = self.get_price_to_earnings_ratio()
    if Stock.fail_high_pe in self._fail:
      rv += "     - :red:`%.2f`\n" % pe
    else:
      rv += "     - %.2f\n" % pe

    cfm = self.get_cash_flow_multiplier()
    if Stock.fail_cfm_lt_pe in self._fail:
      rv += "     - :red:`%.2f`\n" % cfm
    else:
      rv += "     - %.2f\n" % cfm

    op2s = self.get_operational_profit_to_sales_ratio()
    if Stock.fail_op2s_small in self._fail:
      rv += "     - :red:`%.1f%%`\n" % (100*op2s)
    else:
      rv += "     - %.2f%%\n" % (100*op2s)

    np2s = self.get_net_profit_to_sales_ratio()
    if Stock.fail_np2s_small in self._fail:
      rv += "     - :red:`%.1f%%`\n" % (100*np2s)
    else:
      rv += "     - %.2f%%\n" % (100*np2s)

    davg = self.get_dividend_average()
    if Stock.fail_avg_dvdnd_small or Stock.fail_avg_dvdnd_large:
      rv += "     - :red:`A:%.1f`," % davg
    else:
      rv += "     - A: %.1f," % davg

    dstd = self.get_dividend_stdev()
    if Stock.fail_std_dvdnd_large:
      rv += " :red:`S:%.1f`\n" % dstd
    else:
      rv += "S:%.1f\n\n" % dstd

    rv += "     -\n\n"
    rv += "       .. image:: _static/png/dividend_%d.png\n\n" % self.get_id()

    rv += "     - 12m:%.1f\n" % self.get_12month_return()

    rv += "     -\n\n"
    rv += "       .. image:: _static/png/return_%d.png\n\n" % self.get_id()

    earnings_polyfit = self.polyfit(self.get_four_year_data(Stock.earnings_key))
    rv += "     - %.2f,%d%%\n" % (earnings_polyfit[0], 100*earnings_polyfit[1])

    rv += "     -\n\n"
    rv += "       .. image:: _static/png/earnings_%d.png\n\n" % self.get_id()

    op_polyfit = self.polyfit(self.get_four_year_data(Stock.operational_profit_key))
    rv += "     - %.2f,%.0f%%\n" % (op_polyfit[0], 100*op_polyfit[1])

    rv += "     -\n\n"
    rv += "       .. image:: _static/png/operational_profit_%d.png\n\n" % self.get_id()

    self.generate_figures()

    return rv

  # raw data

  def get_id(self) -> int:
    return int(self._data['id'])

  def set_name(self, name: str):
    self._data['name'] = name
    return self

  def get_name(self) -> str:
    return self._data['name']

  def set_price(self, price: float):
    self._data['price'] = str(price)
    return self

  def get_price(self) -> float:
    try:
      return float(self._data['price'])
    except:
      return 0

  def set_price_and_market_capital(self, price: float, market_capital: float):
    self._data['price'] = str(price)
    # self._data['market_capital'] = str(market_capital)
    self._data['number_of_shares'] = str( market_capital / price )
    if 'market_capital' in self._data.keys():
      del self._data['market_capital']
    return self

  def get_market_capital(self) -> float:
    if not 'number_of_shares' in self._data.keys():
      try:
        return float(self._data['market_capital'])
      except:
        return 0

    try:
      return float(self._data['price']) * float(self._data['number_of_shares'])
    except:
      return 0

  eps_key                       = "EPS"
  cash_flow_from_operations_key = "cash_flow_from_operations"
  dividend_key                  = "dividend"
  earnings_key                  = "earnings"
  operational_profit_key        = "operational_profit"
  return_key                    = "return"
  sales_key                     = "sales"
  net_profit_key                = "net_profit"

  def set_annual_data(self, name: str, year: int, data: float):
    self._data["A %s %d" % (name, year)] = str(data)
    return self

  def get_data(self, key: str, nitems: int):
    keys = sorted(filter(lambda x:key in x, self._data.keys()), reverse=True)

    rv = []
    for key in keys:
      rv.append(float(self._data[key]))
      if len(rv) == nitems: break

    return rv

  def get_annual_data(self, key: str, nitems: int = 0):
    return self.get_data("A " + key, nitems)

  def set_quarter_data(self, name: str, year: int, quarter: int, cash_from_from_operations: float):
    self._data["Q %s %d %d" % (name, year, quarter)] = str(cash_from_from_operations)

  def get_quarter_data(self, key: str, nitems: int = 0):
    return self. get_data("Q " + key, nitems)

  # calculations

  @staticmethod
  def sort(o):
    return o.get_score()

  fail_high_pe              = [0, "High P/E"]
  fail_cfm_lt_pe            = [0, "CFM is larger than P/E"]
  fail_cfm_negative         = [0, "CFM negative"]
  fail_op2s_small           = [0, "Operational profit to sales ratio smaller than 10%"]
  fail_np2s_small           = [0, "Net profit to sales ratio smaller than 4%"]
  fail_avg_dvdnd_small      = [0.5, "Average dividend below 3%"]
  fail_std_dvdnd_large      = [0.5, "Dividend STD is larger than 15%"]
  fail_avg_return_small     = [1, "Average return is less than 10%"]
  fail_avg_dvdnd_large      = [1, "Dividend is more than 50% of return."]
  fail_12month_return_small = [1, "12 month return is less than 10%"]


  def get_score(self):
    pe = self.get_price_to_earnings_ratio()
    cfm = self.get_cash_flow_multiplier()
    op2s = self.get_operational_profit_to_sales_ratio()
    np2s = self.get_net_profit_to_sales_ratio()
    davg = self.get_dividend_average()
    dstd = self.get_dividend_stdev()
    ravg = statistics.mean(self.get_five_year_return())
    rlast = self.get_12month_return()

    fail = []

    if pe > 15:                        fail.append(Stock.fail_high_pe)
    if cfm > pe:                       fail.append(Stock.fail_cfm_lt_pe)     # Cash flow multiplier < price to earnings ratio
    if cfm < 0:                        fail.append(Stock.fail_cfm_negative)  # Cash flow should be positive
    if op2s < 0.10:                    fail.append(Stock.fail_op2s_small)    # Operational profit to sales ratio > 5%
    if np2s < 0.04:                    fail.append(Stock.fail_np2s_small)    # Net profit to sales ratio > 4%
    if davg < 3:                       fail.append(Stock.fail_avg_dvdnd_small) # Average dividend above 3%
    # if davg and dstd / davg > 0.15:    fail.append(Stock.fail_std_dvdnd_large) 
    if ravg < 10:                      fail.append(Stock.fail_avg_return_small)
    if davg > 0.5 * ravg:              fail.append(Stock.fail_avg_dvdnd_large)
    if rlast < 10:                     fail.append(Stock.fail_12month_return_small)

    self._fail = fail

    if self.get_id() == 1082379:
      print("%s" % fail)

    if len(fail) > 0:
      score = numpy.prod([i[0] for i in fail])
      return score
    
    return 15-pe

  #steady rise in annual earnings + operational profit

  def get_latest_eps(self):
    # Look at last four quarters if possible
    eps = sum(self.get_quarter_data(Stock.eps_key, 4))
    if eps: return eps

    # If no quarter data -> return data from last year ...
    try:
      return self.get_annual_data(Stock.eps_key, 1)[0]
    except:
      return 0

  def get_price_to_earnings_ratio(self) -> float:
    latest_eps = self.get_latest_eps()
    if latest_eps:
      return (self.get_price() / 100) / latest_eps
    else:
      return 0

  def get_cash_flow_multiplier(self):
    # look at the cash flow from current activity of the last four quarters
    # and not the last year
    data = self.get_quarter_data(Stock.cash_flow_from_operations_key, 4)

    cash_flow_from_operations = sum(data)

    if len(data) < 4 or cash_flow_from_operations == 0:
      return 0

    return self.get_market_capital() / cash_flow_from_operations

  def get_operational_profit_to_sales_ratio(self):
    # look at the cash flow from current activity of the last four quarters
    # and not the last year
    # Note: Calcalist looks only at last quarter
    operational_profit_data = self.get_quarter_data(Stock.operational_profit_key, 4)
    sales_data = self.get_quarter_data(Stock.sales_key, 4)

    operational_profit = sum(operational_profit_data)
    sales = sum(sales_data)

    if len(operational_profit_data) < 4 or len(sales_data) < 4 or sales == 0:
      return 0

    return operational_profit / sales

  def get_net_profit_to_sales_ratio(self):
    # look at the cash flow from current activity of the last four quarters
    # and not the last year
    # Note: Calcalist looks only at last quarter
    sales_data = self.get_quarter_data(Stock.sales_key, 4)
    net_profit_data = self.get_quarter_data(Stock.net_profit_key, 4)

    sales = sum(sales_data)
    net_profit = sum(net_profit_data)

    if len(sales_data) < 4 or len(net_profit_data) < 4 or sales == 0:
      return 0

    return net_profit / sales

  def get_dividend_average(self):
    return statistics.mean(self.get_four_year_data(Stock.dividend_key))

  def get_dividend_stdev(self):
    return statistics.stdev(self.get_four_year_data(Stock.dividend_key))
  
  def get_five_year_return(self):
    returns = []
    for year in range(2015,2020):
      try:
        returns.append(float(self._data["A %s %d" % (Stock.return_key, year)]))
      except:
        returns.append(0)
      
    return returns

  def get_12month_return(self):
      try:
        return float(self._data["A %s %d" % (Stock.return_key, 2019)])
      except:
        return 0

  def get_four_year_data(self, key: str) -> []:
    data = []
    for year in range(2015,2019):
      try:
        data.append(float(self._data["A %s %d" % (key, year)]))
      except:
        data.append(0)

    return data

  def polyfit(self, data: []):
    (p, residuals, rank, singular_values, rcond) = numpy.polyfit(range(0,len(data)), data, 1, full=True)
    #p[0] is the slope]
    #p[1] is the x axis
    #if (statistics.mean(data)):
    #print("%s %d %d %s" % (data, p[0], statistics.mean(data), residuals))
    if sum(data):
      return (p[0] / statistics.mean(data), (residuals[0]/4)**0.5 / statistics.mean(data))
    else:
      return(0,0)

  def generate_bar_graph(self, data: [], filename: str):
    nbars = len(data)

    if min(data) < 0:
      data_range = max(data) - min(data)
      data_min = min(data)
    else:
      data_range = max(data)
      data_min = 0

    width = 1 + nbars * (1 + 3)
    height = 20

    a = [[255,255,255]*(width*3) for item in range(height)]

    if data_range:
      for bar in range(0, nbars):

        bar_x = 4 * bar

        ystart = (data[bar]-data_min)/data_range
        yzero  = (0        -data_min)/data_range
        #print("start, zero %d %d" % (ystart, yzero))
        if ystart < 0:
          (ystart, yend) = (yzero, ystart)
        else:
          yend = yzero

        #print("%f %f %f" % (data[bar], data_min, data_range))
        #print("%d %d" % (ystart, yend))

        ystart = int(height*(1-ystart))
        yend   = int(height*(1-yend))

        for y in range(ystart, yend):
          for x in range(0,9):
            xi = 3 * bar_x + x

            #print("w h x y %s %d %d bar: %d %d %d %d %d" % (data, ystart, yend, bar, width, height, x,y))

            a[y][3*xi + 0] = 0
            a[y][3*xi + 1] = 0
            a[y][3*xi + 2] = 0

    f = open(filename, 'wb')
    w = png.Writer(width*3, height, greyscale=False)
    w.write(f, a)
    f.close()

  def generate_figures(self):
    # print("%d" % self.get_id())
    self.generate_bar_graph(self.get_four_year_data(Stock.dividend_key), 'source/_static/png/dividend_%d.png' % self.get_id())
    self.generate_bar_graph(self.get_five_year_return(), 'source/_static/png/return_%d.png' % self.get_id())
    self.generate_bar_graph(self.get_four_year_data(Stock.earnings_key), 'source/_static/png/earnings_%d.png' % self.get_id())
    self.generate_bar_graph(self.get_four_year_data(Stock.operational_profit_key), 'source/_static/png/operational_profit_%d.png' % self.get_id())

def to_float(s: str) -> float:
  if s == "--":
    return 0
  else:
    return locale.atof(s)

def get_value(driver, path) -> float:
  element = driver.find_element_by_xpath(path)
  return to_float(element.text)

def scrub_prices(stocks):
  locale.setlocale( locale.LC_ALL, 'en_US.UTF-8' ) 
  driver = webdriver.Chrome(executable_path = 'C:/Program Files (x86)/Google/Chrome/Application/chromedriver.exe')
  driver.get("https://info.tase.co.il/heb/marketdata/stocks/marketdata/Pages/MarketData.aspx")
  time.sleep(2)

  f = open("test1.txt", "wb")

  for page in range(1,10):

    row = 2
    while 1:
      path = '*[@id="ctl00_ctl40_g_55dc650a_ae63_4190_ad5a_3c40a8114974_ctl00_ucGridAllShares_DataGrid1"]/tbody/tr[%d]' % row
      path = '*[@id="*_ucGridAllShares_DataGrid1"]/tbody/tr[%d]' % row
      path = '//*[contains(@id, "_ucGridAllShares_DataGrid1")]/tbody/tr[%d]' % row

      price_path = path + "/td[6]" # + "/td[6]/div"
      stock_id_path = path + "/td[8]" # /div"
      market_capital_path = path + "/td[8]" # /div"

      try:
        stock_id_result = driver.find_element_by_xpath(stock_id_path)
        price_result = driver.find_element_by_xpath(price_path)
        market_capital_result = driver.find_element_by_xpath(market_capital_path)
      except:
        break

      stock_id = int(stock_id_result.text)
      price = float(price_result.text.replace(',', ''))
      market_capital = float(market_capital_result.text.replace(',', ''))

      f.write(("%s: %s\n" % (stock_id, price)).encode("utf-8"))

      stocks[stock_id].set_price(price)

      row = row + 1

    if page < 9:
      # click next page number
      element = driver.find_element_by_link_text("%d" % (page+1))
      element.click()
      time.sleep(4)

  f.close()
  driver.quit()

def scrub_stock(driver, stock: Stock):

  #f = open("test1.txt", "wb")
  #f.close()

  stock_id = stock.get_id()


  general_view_path = "https://www.bizportal.co.il/capitalmarket/quote/generalview/%d" % stock_id
  profile_path      = "https://www.bizportal.co.il/capitalmarket/quote/profile/%d" % stock_id
  performance_path  = "https://www.bizportal.co.il/capitalmarket/quote/performance/%d" % stock_id

  # reports
  # -------
  reports_path = "https://www.bizportal.co.il/capitalmarket/quote/reports/%d" % stock_id
  driver.get(reports_path)
  time.sleep(4)

  results = driver.find_elements_by_xpath("//table[@id='profit-and-loss-report']")
  for result in results:
    # skip hidden data
    if result.location['x'] == 0: continue

    rows = result.find_elements(By.TAG_NAME, "tr") # get all of the rows in the table

    # Process heading
    years = []
    quarters = []
    cols = rows[0].find_elements(By.TAG_NAME, "th")
    for ci in range(0,len(cols)):
      m = re.match(r'Q(\d)\/(\d+)', cols[ci].text)
      if m:
        quarters.append(int("0"+m.group(1)))
        years.append(int("0"+m.group(2)))
      else:
        quarters.append(0)
        years.append(0)

    cols = rows[1].find_elements(By.TAG_NAME, "td")
    for ci in range(1,len(cols)):
      stock.set_quarter_data(Stock.sales_key, years[ci], quarters[ci], to_float(cols[ci].text))

    cols = rows[3].find_elements(By.TAG_NAME, "td")
    for ci in range(1,len(cols)):
      stock.set_quarter_data(Stock.operational_profit_key, years[ci], quarters[ci], to_float(cols[ci].text))

    cols = rows[6].find_elements(By.TAG_NAME, "td")
    for ci in range(1,len(cols)):
      stock.set_quarter_data(Stock.net_profit_key, years[ci], quarters[ci], to_float(cols[ci].text))

    cols = rows[9].find_elements(By.TAG_NAME, "td")
    for ci in range(1,len(cols)):
      stock.set_quarter_data(Stock.eps_key, years[ci], quarters[ci], to_float(cols[ci].text))


  results = driver.find_elements_by_xpath("//table[@id='cash-flow-report']")
  for result in results:
    # skip hidden data
    if result.location['x'] == 0: continue

    rows = result.find_elements(By.TAG_NAME, "tr") # get all of the rows in the table

    # Process heading
    years = []
    quarters = []
    cols = rows[0].find_elements(By.TAG_NAME, "th")
    for ci in range(0,len(cols)):
      m = re.match(r'Q(\d)\/(\d+)', cols[ci].text)
      try:
        quarters.append(int("0"+m.group(1)))
        years.append(int("0"+m.group(2)))
      except:
        quarters.append(0)
        years.append(0)

    # Cash flow from operations is row 1
    cols = rows[1].find_elements(By.TAG_NAME, "td")
    for ci in range(1,len(cols)):
      stock.set_quarter_data(Stock.cash_flow_from_operations_key, years[ci], quarters[ci], to_float(cols[ci].text))


  # click for annual data
  element = driver.find_element_by_css_selector("li[aria-controls='profit-and-loss-report-tabstrip-2']")
  element.click()
  time.sleep(4)

  results = driver.find_elements_by_xpath("//table[@id='profit-and-loss-report']")
  for result in results:
    # skip hidden table (which is the quarterly values)
    if result.location['x'] == 0: continue

    rows = result.find_elements(By.TAG_NAME, "tr") # get all of the rows in the table

    # Process heading
    years = []
    cols = rows[0].find_elements(By.TAG_NAME, "th")
    for ci in range(0, len(cols)):
      year = "0"+cols[ci].text
      years.append(int(year.replace('0Y/','')))
      #f.write(("th (%d) %s\n" % (ci, cols[ci].text)).encode("utf-8"))
      #annual_data.append({})
      #annual_data[ci-1]['year'] = cols[ci].text

    # EPS is row 9
    cols = rows[9].find_elements(By.TAG_NAME, "td")
    for ci in range(1, len(cols)):
      stock.set_annual_data(Stock.eps_key, years[ci], to_float(cols[ci].text))

    # Earnings is row 1
    cols = rows[1].find_elements(By.TAG_NAME, "td")
    for ci in range(1, len(cols)):
      stock.set_annual_data(Stock.earnings_key, years[ci], to_float(cols[ci].text))

    # Operational profit is row 3
    cols = rows[3].find_elements(By.TAG_NAME, "td")
    for ci in range(1, len(cols)):
      stock.set_annual_data(Stock.operational_profit_key, years[ci], to_float(cols[ci].text))

  # performance
  # -----------
  driver.get(performance_path)
  time.sleep(2)

  try:
    result = driver.find_element_by_xpath("//article[@class='center-part section-container']/div/div/div[4]/div/table/tbody")
    rows = result.find_elements(By.TAG_NAME, "tr") # get all of the rows in the table
    for row in rows:
      cols = row.find_elements(By.TAG_NAME, "td")
      stock.set_annual_data(Stock.dividend_key, locale.atoi(cols[0].text), locale.atof(cols[4].text))
  except:
    i = 1
    
  result = driver.find_element_by_xpath("//article[@class='center-part section-container']/div/div[1]/div[1]/div/div[2]/table/tbody")
  rows = result.find_elements(By.TAG_NAME, "tr") # get all of the rows in the table

  first_row = True
  for row in rows:
    cols = row.find_elements(By.TAG_NAME, "td")

    # first row is last 12 months -> use as 2019 value
    if first_row:
      stock.set_annual_data(Stock.return_key, 2019, to_float(cols[1].text))
      first_row = False

    m = re.search(r'(20\d+)', cols[0].text)
    if m:
      stock.set_annual_data(Stock.return_key, int(m.group(1)), to_float(cols[1].text))

  # get price, market_capital
  # -------------------------
  driver.get(general_view_path)
  time.sleep(2)
  price = get_value(driver, "//div[@class='col-lg-6 no-padding paper-data']/div/div[2]/ul/li[1]/span[@class='num']")
  market_capital = get_value(driver, "//div[@class='col-lg-6 no-padding paper-data']/div/div[2]/ul/li[7]/span[@class='num']")

  stock.set_price_and_market_capital(price, market_capital)

  # print("price %f market_capital %d" % (price, market_capital))

  # driver.get(profile_path)
  # stock.set_name(get_string(driver, "//div[@class='content-area company-profile']/div/div/div/div[12]"))

  return stock

def scrub_all(stocks, start: int):
  locale.setlocale( locale.LC_ALL, 'en_US.UTF-8' ) 
  driver = webdriver.Chrome(executable_path = 'C:/Program Files (x86)/Google/Chrome/Application/chromedriver.exe')

  for stock_id in sorted(stocks.keys()):
    if stock_id < start: continue
    if stocks[stock_id].skip(): continue
    print("processing stock: %d" % stock_id, flush=True)
    scrub_stock(driver, stocks[stock_id])
    
    write_stock_data(stocks)

  driver.quit()

def scrub_one(stocks, stock_id: int):
  locale.setlocale( locale.LC_ALL, 'en_US.UTF-8' ) 
  driver = webdriver.Chrome(executable_path = 'C:/Program Files (x86)/Google/Chrome/Application/chromedriver.exe')

  print("processing stock: %d" % stock_id, flush=True)
  scrub_stock(driver, stocks[stock_id])
  write_stock_data(stocks)

  driver.quit()

def scrub_all(stocks, start: int):
  locale.setlocale( locale.LC_ALL, 'en_US.UTF-8' ) 
  driver = webdriver.Chrome(executable_path = 'C:/Program Files (x86)/Google/Chrome/Application/chromedriver.exe')

  for stock_id in sorted(stocks.keys()):
    if stock_id < start: continue
    if stocks[stock_id].skip(): continue
    print("processing stock: %d" % stock_id, flush=True)
    scrub_stock(driver, stocks[stock_id])
    
    write_stock_data(stocks)

  driver.quit()

def read_stock_data():
  stocks = {}

  f = open(args.read_stock_data, "r", encoding='utf-8')
  stocks_data = f.read().split("stock data:\n")

  for stock_data in stocks_data:
    if stock_data:
      stock = Stock('New').load_from_str(stock_data)
      stocks[stock.get_id()] = stock

  f.close()

  return stocks

def write_stock_data(stocks):
  f = open(args.write_stock_data, "w", encoding='utf-8')
  for stock_id in sorted(stocks.keys()):
    f.write("stock data:\n")
    f.write(stocks[stock_id].as_str())
  f.close()

def write_sphinx(stocks: []):
  f = open("source/stock_list.txt", "w", encoding='utf-8')

  f.write(".. list-table:: \n")
  f.write("  :header-rows: 1\n")
  # f.write("  :widths: 3 1 1 1 1 1 1 1 1 10 1 3 1 2 1 3 1\n")
  f.write("\n")
  f.write(Stock.get_stock_list_header())
  for stock in sorted(stocks.values(), key=Stock.sort, reverse=1):
    f.write(stock.get_stock_list_row())

  f.close()

# https://www.bizportal.co.il/tradedata/paperslist
if __name__ == "__main__":
  # sys.stdout = codecs.getwriter('utf8')(sys.stdout)
  # sys.stderr = codecs.getwriter('utf8')(sys.stderr)
  sys.stdout.flush()

  parser = argparse.ArgumentParser(description='Stock scrubber')
  parser.add_argument("--read_stock_data", default="stock_data.txt", type=str, help="Reads stock data from file.")
  parser.add_argument("--init_stock_data", default=None, type=str, help="Init stock data file from CSV list.")
  parser.add_argument("--scrub_prices", default=False, help="Goes over all stocks and reads prices.")
  parser.add_argument("--scrub_all", default=False, help="Goes over all stocks and reads all data.")
  parser.add_argument("--scrub_one", default=0, type=int, help="Scrube one stock.")
  parser.add_argument("--scrub_start", default=0, type=int, help="Goes over all stocks and reads all data.")
  parser.add_argument("--write_sphinx", default=1, type=int, help="Generate sphinx data.")
  parser.add_argument("--write_stock_data", default=None, type=str, help="After all processing write stock data to file.")
  args = parser.parse_args()

  stocks = {}

  if args.read_stock_data:
    stocks = read_stock_data()

  if args.init_stock_data:
    f = open(args.init_stock_data, "r", encoding='utf-8')
    lines = f.read().splitlines()
    for line in lines:
      (stock_name, stock_id) = line.split(",")
      stocks[int(stock_id)] = Stock(stock_id).set_name(stock_name)
    f.close()

  if args.scrub_prices:
    scrub_prices(stocks)

  if args.scrub_one:
    scrub_one(stocks, args.scrub_one)

  if args.scrub_all:
    scrub_all(stocks, args.scrub_start)

  if args.write_stock_data:
    write_stock_data(stocks)

  if args.write_sphinx:
    write_sphinx(stocks)

  '''
Price to earnings ratio < 15
Cash flow multiplier < price to earnings ratio
Operational profit to sales ratio > 5%
Net profit to sales ratio > 4%
Dividend history - stable and above threshold
steady rise in return
make sure dividen is no more than 50% return
'''

