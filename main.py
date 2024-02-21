from PyQt5.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget, QFileDialog, QTextEdit, QMessageBox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
import json
import time
from licensing.models import *
from licensing.methods import Key, Helpers

class PostWindow(QWidget):
    def __init__(self, driver, login_window):
        super().__init__()
        self.driver = driver
        self.login_window = login_window  # Store reference to the login window
        self.setWindowTitle("Add Post Content")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.message_label = QLabel("Post Content:")
        self.message_edit = QTextEdit()
        layout.addWidget(self.message_label)
        layout.addWidget(self.message_edit)

        self.image_button = QPushButton("Select Image(s)")
        self.image_button.clicked.connect(self.select_images)
        layout.addWidget(self.image_button)

        self.group_label = QLabel("Group Links (one per line):")
        self.group_edit = QTextEdit()
        layout.addWidget(self.group_label)
        layout.addWidget(self.group_edit)

        self.get_links_button = QPushButton("Get All Group Links")
        self.get_links_button.clicked.connect(self.get_all_group_links)
        layout.addWidget(self.get_links_button)

        self.post_button = QPushButton("Post")
        self.post_button.clicked.connect(self.post)
        layout.addWidget(self.post_button)

        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        layout.addWidget(self.logout_button)

        self.setLayout(layout)
        self.image_paths = []

    def get_all_group_links(self):
        # Navigate to the URL
        self.driver.get("https://mbasic.facebook.com/groups/?seemore")
        
        # Find the element containing the group links
        try:
            group_list_element = self.driver.find_element(By.XPATH, '//*[@id="root"]/table/tbody/tr/td/div[2]/ul')
        except NoSuchElementException:
            QMessageBox.warning(self, "Error", "Group links not found.")
            return

        # Find all links within the element
        links = group_list_element.find_elements(By.TAG_NAME, 'a')

        # Extract and append the href attribute of each link to the group edit box
        group_links = []
        for link in links:
            group_link = link.get_attribute('href')
            if group_link and "/groups/" in group_link:
                self.group_edit.append(group_link)
                group_links.append(group_link)
        
        QMessageBox.information(self, "Success", f"{len(group_links)} group links retrieved successfully.")
        return group_links


    def select_images(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Image(s)", "", "Image Files (*.jpg *.png *.jpeg)", options=options)
        if file_paths:
            self.image_paths.extend(file_paths)

    def post(self):
        message = self.message_edit.toPlainText()
        group_links = self.group_edit.toPlainText().splitlines()

        if not message:
            QMessageBox.warning(self, "Warning", "Please enter post content.")
            return

        if not group_links:
            QMessageBox.warning(self, "Warning", "Please enter group links.")
            return

        if not self.image_paths:
            QMessageBox.warning(self, "Warning", "Please select at least one image.")
            return

        for group_link in group_links:
            print(f"Posting to group: {group_link}")

            try:
                self.driver.get(group_link)
                print(f"Opened group: {group_link}")

            except Exception as e:
                print(f"Error navigating to group: {group_link}")
                print(e)
                continue

            post_text = self.driver.find_element(By.NAME, "xc_message")
            post_text.send_keys(message)

            for i, image_path in enumerate(self.image_paths, start=1):
                upload_photo = self.driver.find_element(By.XPATH, f'//input[@name="view_photo"]')
                upload_photo.click()
                upload_input = self.driver.find_element(By.XPATH, f'//input[@name="file{i}"]') if i <= 3 else self.driver.find_element(By.XPATH, f'//input[@name="file3"]')
                upload_input.send_keys(image_path)
                
                # Add a delay to ensure the file is uploaded before clicking "Done"
                time.sleep(2)

                try:
                    upload_done = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//input[@name="add_photo_done"]')))
                    upload_done.click()
                except NoSuchElementException:
                    print("Error: 'Done' button not found.")
                    break  # Break the loop if "Done" button is not found or clickable

            print("Posting...")
            post_btn = self.driver.find_element(By.XPATH, '//input[@name="view_post"]')
            post_btn.click()
            print("Posted.")

    def logout(self):
        if self.driver:
            self.driver.quit()  # Quit the Chrome browser
        self.login_window.show()  # Show the login window
        self.close()  # Close the post window

class LoginWindow(QWidget):
    CONFIG_FILE = 'login_config.json'

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setGeometry(100, 100, 300, 250)

        layout = QVBoxLayout()

        self.email_phone_label = QLabel("Email or Phone Number:")
        self.email_phone_edit = QLineEdit()
        layout.addWidget(self.email_phone_label)
        layout.addWidget(self.email_phone_edit)

        self.password_label = QLabel("Password:")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_edit)

        self.license_key_label = QLabel("License Key:")
        self.license_key_edit = QLineEdit()
        layout.addWidget(self.license_key_label)
        layout.addWidget(self.license_key_edit)

        self.activate_button = QPushButton("Activate License")
        self.activate_button.clicked.connect(self.activate_license)
        layout.addWidget(self.activate_button)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.login)
        self.login_button.setEnabled(False)  # Initially disable the login button
        layout.addWidget(self.login_button)

        self.setLayout(layout)
        self.driver = None

        self.load_credentials()  # Load saved credentials

    def load_credentials(self):
        try:
            with open(self.CONFIG_FILE, 'r') as file:
                credentials = json.load(file)
                if 'email' in credentials:
                    self.email_phone_edit.setText(credentials['email'])
                if 'password' in credentials:
                    self.password_edit.setText(credentials['password'])
                if 'license_key' in credentials:
                    self.license_key_edit.setText(credentials['license_key'])
        except FileNotFoundError:
            pass

    def save_credentials(self, email, password, license_key):
        credentials = {'email': email, 'password': password, 'license_key': license_key}
        with open(self.CONFIG_FILE, 'w') as file:
            json.dump(credentials, file)

    def activate_license(self):
        RSAPubKey = "<RSAKeyValue><Modulus>wWWWLy7xypS0CoNaTd+K1+tsifh0xdBkT98sSSha+b2IL/4zZPdPZeFhbM2kL7ZMwAF6nHFnRIOwASXycmEUJ7BGcdXjdYow3bTelZpeDdY6hAxaryl0Fd4tR/kaGkZcZ3vyWbC8frAko73tt+oir6H9xjM/mcuW42OfMLT/oAA30iUW46qGnbAOfwhrTWIDHK7fPX61ZAUKbvvYEAUm+0yAADfcm2/fkWL9olzTZRrwGvmOURlPdO3bNpCYXeWJpx+gX3mMDeVmc87iebDAZHCI9soGlwsWrzE63S18F9qYNYuX4inBMLktFFawteCDib5qdk7yeRcgbJid7KUqnQ==</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>"
        auth = "WyI3NTQzNzk0NCIsIlAyRTdXcEMrQmZCMTh6L1BKTW5BblplTjh3R1BvT1NQOUNDbS9QZTgiXQ=="
        entered_key = self.license_key_edit.text()

        result = Key.activate(token=auth,\
                              rsa_pub_key=RSAPubKey,\
                              product_id=24173, \
                              key=entered_key, 
                              machine_code=Helpers.GetMachineCode())

        if result[0] == None or not Helpers.IsOnRightMachine(result[0]):
            # an error occurred or the key is invalid or it cannot be activated
            # (e.g., the limit of activated devices was achieved)
            QMessageBox.warning(self, "License Activation", f"The license does not work: {result[1]}")
        else:
            # everything went fine if we are here!
            QMessageBox.information(self, "License Activation", "The license is valid!")
            self.login_button.setEnabled(True)  # Enable the login button after successful license activation

    def login(self):
        email_txt = self.email_phone_edit.text()
        pwd_txt = self.password_edit.text()

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_experimental_option("excludeSwitches", ['enable-automation'])
        options = Options()
        options.add_argument('disable-infobars')

        print("Starting Chrome...")
        self.driver = webdriver.Chrome(options=chrome_options)
        print("Chrome started.")

        print("Opening Facebook login page...")
        self.driver.get('https://fb.com/')
        print("Facebook login page opened.")

        wait = WebDriverWait(self.driver, 10)
        email = wait.until(EC.visibility_of_element_located((By.ID, 'email')))
        print("Logging in to Facebook...")
        email.send_keys(email_txt)
        print("Email entered.")

        pwd = wait.until(EC.visibility_of_element_located((By.ID, 'pass')))
        pwd.send_keys(pwd_txt)
        print("Password entered.")

        login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log in')]")))
        login_btn.submit()
        print("Login button clicked. Logging in...")
        print("Logged in to Facebook.")

        self.save_credentials(email_txt, pwd_txt, self.license_key_edit.text())  # Save credentials and license key

        self.post_window = PostWindow(self.driver, self)
        self.hide()  # Hide the login window after successful login
        self.post_window.show()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())
