from main import search_records


for i in range(1, 1753+1):
    search_records(2023, 1, 99999, "complete_2023.txt", i)
