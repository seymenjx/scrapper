from functions import process_line

pageurl = "https://karararama.yargitay.gov.tr/"
for line in [[2015, 1, 5044, 999999]]:
    process_line(line[0], pageurl, line[1], line[2], line[3])
