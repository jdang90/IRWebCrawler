from analytics import analytics

tokens = ["research"] * 60
analytics.add_page("https://vision.ics.uci.edu/page#section", tokens=tokens)
analytics.write_report()
print("Done. Check crawl_report.txt")
