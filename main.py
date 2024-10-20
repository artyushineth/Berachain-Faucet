from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
import requests
import time


# функция для чтения файла с ID и кошельками
def read_wallets(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    return [line.strip().split('-') for line in lines]


# функция для решения CAPTCHA
def capsolver(api_key_val, site_key_val, site_url_val):
    payload = {
        "clientKey": api_key_val,
        "task": {
            "type": 'AntiTurnstileTaskProxyLess',
            "websiteKey": site_key_val,
            "websiteURL": site_url_val,
            "metadata": {
                "action": ""
            }
        }
    }
    res = requests.post("https://api.capsolver.com/createTask", json=payload)
    resp = res.json()
    task_id = resp.get("taskId")
    if not task_id:
        return

    while True:
        time.sleep(1)
        payload = {"clientKey": api_key_val, "taskId": task_id}
        res = requests.post("https://api.capsolver.com/getTaskResult", json=payload)
        resp = res.json()
        status = resp.get("status")
        if status == "ready":
            return resp.get("solution", {}).get('token')
        if status == "failed" or resp.get("errorId"):
            return


# функция для работы с конкретным user_id и кошельком
def process_user(user_id, wallet, api_key, site_key, site_url):
    try:
        # запуск браузера Adspower
        open_url = f"http://local.adspower.net:50325/api/v1/browser/start?user_id={user_id}"
        response = requests.get(open_url).json()

        # получаем путь к webdriver и адрес WebSocket от Adspower
        chrome_driver = response["data"]["webdriver"]
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", response["data"]["ws"]["selenium"])

        # настройка Selenium WebDriver
        service = Service(executable_path=chrome_driver)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # загрузка целевой страницы
        time.sleep(2)
        driver.get(site_url)
        time.sleep(3)

        # решение CAPTCHA и получение токена
        token = capsolver(api_key, site_key, site_url)

        # вставка токена CAPTCHA в форму
        if token:
            try:
                # проверим, не находится ли CAPTCHA внутри iframe
                iframes = driver.find_elements(By.TAG_NAME, 'iframe')
                captcha_element = None

                # проходим по всем iframe, чтобы найти нужный элемент
                for iframe in iframes:
                    driver.switch_to.frame(iframe)
                    try:
                        captcha_element = driver.find_element(By.NAME, "cf-turnstile-response")
                        if captcha_element:
                            break
                    except NoSuchElementException:
                        # если не найдено, переключаемся обратно на основной контекст
                        driver.switch_to.default_content()

                # если элемент не был найден в iframe, пробуем искать на основном контексте
                if not captcha_element:
                    driver.switch_to.default_content()
                    captcha_element = driver.find_element(By.NAME, "cf-turnstile-response")

                # вставляем решённый токен в поле CAPTCHA
                driver.execute_script("arguments[0].value = arguments[1];", captcha_element, token)

                # диспетчеризация события изменения, чтобы имитировать ввод пользователя
                driver.execute_script(
                    'document.getElementsByName("cf-turnstile-response")[0].dispatchEvent(new Event("change"));'
                )

                # переключение обратно на основной контекст страницы
                driver.switch_to.default_content()

                # вставка крипто-кошелька
                wallet_input = driver.find_element(By.XPATH,
                                                   '/html/body/div[2]/main/div/div[1]/div[1]/div[2]/div[2]/div/input')
                wallet_input.send_keys(wallet)
                time.sleep(1)  # пауза перед нажатием на кнопку

                # нажимаем на кнопку
                submit_button = driver.find_element(By.XPATH, '/html/body/div[2]/main/div/div[1]/div[1]/div[3]/button')
                submit_button.click()

                print(f"Запрошены токены на кошельке: {wallet} для user_id {user_id}.")
            except Exception as e:
                print(f"Ошибка при вставке токена CAPTCHA или отправке формы: {e}")

        # завершение работы с текущим браузером
        time.sleep(2)
        close_url = f"http://local.adspower.net:50325/api/v1/browser/stop?user_id={user_id}"
        requests.get(close_url).json()

    except Exception as e:
        print(f"Ошибка при обработке user_id {user_id}: {e}")


# основная функция
def main():
    # чтение кошельков и user_id
    lines = read_wallets('id.txt')

    # данные для решения CAPTCHA
    api_key_main = "CAP-35ALKJSDLFW3ERWLK324SF67628882D71052E8E6343"  # ваш API ключ от capsolver
    site_key_main = "0x4AAAAAAARdAuciFArKhVwt"  # ключ капчи
    site_url_main = "https://bartio.faucet.berachain.com/"  # URL страницы

    # обрабатываем каждого пользователя
    for user_id, wallet in lines:
        process_user(user_id, wallet, api_key_main, site_key_main, site_url_main)

    # завершение работы со всеми кошельками
    print("На всех кошельках запрошены токены.")


# запуск основного процесса
if __name__ == "__main__":
    main()
