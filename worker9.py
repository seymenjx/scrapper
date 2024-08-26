from functions import process_line
pageurl = "https://karararama.yargitay.gov.tr/"

for line in [[2011, 1, 1542, 999999], [2023, 1, 1611, 999999], [2024, 1, 273, 999999]]:
    process_line(line[0], pageurl, line[1], line[2], line[3])
