from cool_cache import cache

@cache()
def things():
    from time import sleep
    sleep(10)
    return 999
    

print(f'''things = {things()}''')
print(f'''things = {things()}''')
