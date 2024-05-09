'''
29.11.2023

In acest moment aplicatia porneste 3 threaduri pe langa threadul principal al lui main()
* com_listener()
    - verifica periodif bufferul fizic
    - cand dimensiunea datelor din bufferul fizic s-a stabilizat, citeste datele
    - introduce datele citite intr-o lista globala
    - se reintoarce la functia de verificare buffer
    - nu se mai intereseaza de informatia introdusa in lista. asta pentru a nu rata vreo informatie primita


* send_msg
    - foloseste o lista globala ce contine mesaje ce trebuie trimise
    - imediat ce lista contine cel putin un mesaj, functia va trimite mesajele in ordine FIFO
    - am apelat la aceasta metoda deoarece sunt mai multe parti in cod unde trebuie sa trimitem mesaje 
    si am dorit sa nu am problema cu intercalare sau ordinea mesajelor


    
* logger
    - foloseste o lista globala
    - imediat ce lista contine cel putin un mesaj, functia va scoate mesajele FIFO din lista si le va scrie in log
    - am apelat la aceasta varianta pentru a putea trata mesajele ce se genereaza repede, aproape in acelasi timp


12.12.2023
Am inceput sa mut functiile in clase astfel incat sa-mi fie mai usor sa lucrez cu comunicatiile seriale
- cu display-ul DWIN
- cu modulul de moneda Ribao
- cu printerul serial


29.12.2023
Am rezolvat o problema cu threadurile prin care, in anumite conditii, se calcau pe picioare si incepeau sa proceseze greu.
Matheo a venit cu ideea ca trebuie sa implementez mutexuri, astfel incat acum threadurile sunt executate unul dupa altul, nu in paralel.
Asta le ajuta sa nu aiba probleme cu resursele globale pe care le acceseaza 




22.04.2024
Am facut trecerea pe linux si am pus codul pe un miniPC cu porturi RS232 onboard
Am implementat integrarea unei baze de date sqlite in care, in urma fiecarei tranzactii, inserez
- detaliile tranzactiei
- un update asupra nivelului de colectare


26.04.2024
Am renuntat la functiile pt paginile speciale deoarece nu imi permitea integrarea facila pt timere non blocking. 
Ca solutie am implementat tratarea paginilor speciale in threadul Principalul prin activarea unor flaguri specifice


08.05.2024
Am facut modificari in GUI
Am implementat incheierea fluxului de colectare. In acest moment avem 3 tabele
- Transactions - in care sunt inregistrate fiecare tranzactie cu timp de inceput si sfarsit
- Storage - in care se acumuleaza fiecare tranzactie. Starttime se copiaza de la inregistrarea precedenta
- Collection - contine inregistrarile cand s-a efectuat o colectare a containerelor


09.05.2024
Am implementat generarea de chitante, momentan doar in format text

'''





import serial
import time
from datetime import datetime
import random
import concurrent.futures
import logging
import codecs
import os, io, subprocess
import multiprocessing
import sqlite3

ribao_port = '/dev/ttyS0'
dwin_port = '/dev/ttyS1'
baudrate = 115200
random.seed(5)

userID = 1234
userPIN = 5678



motor_check = 0
motor_state = 'ff'
timer = datetime.now()

topage0 = 0


page02 = False
page04 = False
page10 = False
# page12 = False


coin1ban = 0
coin5bani = 0
coin10bani = 0
coin50bani = 0
total = 0

# la apelarea acestei functii, daca s-a atins dimensiunea maxima a fisierului, 
# se sterg primele 1000 de randuri (cele mai vechi)
def file_max(fname, max):
    if os.path.getsize(fname) > max:
        subprocess.call('sed -i \'1,1000d\' ' + fname, shell=True)




def collection_receipt(collection, last_collection):
    try:
        
        filename = collection[6].strftime("Collection_%Y%m%d_%H%M%S.txt")
        foldername = collection[6].strftime("./Receipts/Collection")
        # foldername = collection[6].strftime("./Receipts/Collection/%Y%m%d")
        print(filename)

        if not os.path.exists(foldername):
            os.makedirs(foldername)

        receipt = '''   CHITANTA COLECTARE

------------------------------

Collection no: {coll_no}
Start Time: {starttime}
End Time:   {endtime}


{coin01} x 1 BAN
{coin05} x 5 BANI
{coin10} x 10 BANI
{coin50} x 50 BANI
______________________________
    TOTAL {total:.2f} RON
'''
        try:
            with open(foldername + "/" + filename, 'w+') as receiptfile:
                receiptfile.write (receipt.format(
                    coll_no = last_collection,
                    coin01 = str(collection[0]).rjust(7),
                    coin05 = str(collection[1]).rjust(7),
                    coin10 = str(collection[2]).rjust(7),
                    coin50 = str(collection[3]).rjust(7),
                    total = collection [4],
                    starttime = collection[5].strftime("%H:%M:%S %d.%m.%Y"),
                    endtime = collection[6].strftime("%H:%M:%S %d.%m.%Y")
                ))
        except Exception as e:
            print (e)
    except Exception as e:
        print ("eroare la rularea functiei collection_receipt", e)





def transaction_receipt(collection, last_transaction):
    try:
        
        filename = collection[6].strftime("Coindep_%Y%m%d_%H%M%S.txt")
        foldername = collection[6].strftime("./Receipts/Transactions/%Y%m%d")
        print(filename)

        if not os.path.exists(foldername):
            os.makedirs(foldername)

        receipt = '''   CHITANTA DEPUNERE

------------------------------

Transaction no: {tr_no}
Start Time: {starttime}
End Time:   {endtime}


{coin01} x 1 BAN
{coin05} x 5 BANI
{coin10} x 10 BANI
{coin50} x 50 BANI

------------------------------

    TOTAL {total:.2f} RON
'''
        try:
            with open(foldername + "/" + filename, 'w+') as receiptfile:
                receiptfile.write (receipt.format(
                    tr_no = last_transaction,
                    coin01 = str(collection[0]).rjust(7),
                    coin05 = str(collection[1]).rjust(7),
                    coin10 = str(collection[2]).rjust(7),
                    coin50 = str(collection[3]).rjust(7),
                    total = collection [4],
                    starttime = collection[5].strftime("%H:%M:%S %d.%m.%Y"),
                    endtime = collection[6].strftime("%H:%M:%S %d.%m.%Y")
                ))
        except Exception as e:
            print (e)
    except Exception as e:
        print ("eroare la rularea functiei collection_receipt", e)



def logger(lock):
    global logpool
    
    while True:
        # print("*** #")
        time.sleep(0.01)
        with lock: 
            if len(logpool):
                logging.warning(logpool.pop(0))
           





class Ribao:                                 
    def com_listener(self, ribao_ser, lock):      # Ribao
        global ribao_rcvdmsg
        global logpool

       
        
        while True:
            # print("***    #")
            time.sleep(0.01)
            with lock:
                mesaj = []
                try:
                    if ribao_ser.in_waiting > 4: 
                        for i in range(4):
                            mesaj.append(ribao_ser.read().hex())
                        if mesaj [0] == 'fe' and mesaj [3] == 'ef':
                            for i in range (int(mesaj[2],16)-4):
                                mesaj.append(ribao_ser.read().hex())
                        else:
                            print('\nmesaj not OK')
                            ribao_ser.reset_input_buffer()

                        if mesaj != ['5a', 'a5', '03', '82', '4f', '4b']:
                            ribao_rcvdmsg.append(mesaj)
                            logpool.append('     <#<#<  %a' % mesaj)
                        else:
                            logpool.append('           <  ????')
                        mesaj = []
                except ValueError as error:
                    print(error)

                



    def send_msg(self, ribao_ser, lock):      # Ribao
        global ribao_tobesent
        global logpool

        while True:
            # print("***       #")
            time.sleep(0.01)
            with lock:
                if len(ribao_tobesent):
                    senddata = ribao_tobesent.pop(0)
                    # print(senddata)
                    ribao_ser.write(senddata)

                    temp_list = list(senddata.hex())
                    log_message = []
                    for i in range (0, len(temp_list), 2):
                        log_message.append(temp_list[i] + temp_list[i+1])
                    logpool.append('>#>#>  %a' % log_message)
                    senddata = None
                    
  

    def msginterpret(self, x):      # Ribao
        global coin1ban, coin5bani, coin10bani, coin50bani
        global motor_state
        if len(x) >= 6:
            function = x[4]
            data = []
            for i in range(5, len(x)-1):
                data.append(x[i])
            
            # print(f'functia {function}     data {data}')


            
            match function:
                case 'a1':
                    # print('facem un A1')
                    coin50bani = int(data[0]+data[1], 16)
                    coin10bani = int(data[2]+data[3], 16)
                    coin5bani = int(data[4]+data[5], 16)
                    coin1ban = int(data[6]+data[7], 16)
                    # print('am calculat')
                    try:
                        dwin.display_results(coin1ban, coin5bani, coin10bani, coin50bani)
                    except ValueError as error:
                        print (error)
                    # print('am afisat')

                case 'ad':
                    motor_state = data[0]
                    # print('facem un AD')

                case _:
                    pass
                    # print ('nicio functie')
                
            

                





# clasa functiilor pt display DWIN
class Dwin:                                 
    def com_listener(self, dwin_ser, lock):
        global dwin_rcvdmsg
        global logpool
        
        while True:
            # print("***          #")
            time.sleep(0.01)
            with lock:
                mesaj = []
                if dwin_ser.in_waiting > 3: 
                    for i in range(3):
                        mesaj.append(dwin_ser.read().hex())
                    if mesaj [0:2] == ['5a', 'a5']:
                        for i in range (int(mesaj[2],16)):
                            mesaj.append(dwin_ser.read().hex())
                    else:
                        print('\nmesaj not OK')
                        dwin_ser.reset_input_buffer()

                    if mesaj != ['5a', 'a5', '03', '82', '4f', '4b']:
                        dwin_rcvdmsg.append(mesaj)
                        logpool.append('     <<<<<  %a' % mesaj)
                    else:
                        logpool.append('           <  Dwin OK')
                    mesaj = []
                



    def send_msg(self, dwin_ser, lock):     #Dwin
        global dwin_tobesent
        global logpool

        while True:
            # print("***             #")
            time.sleep(0.01)
            with lock:
                if len(dwin_tobesent):
                    senddata = dwin_tobesent.pop(0)
                    dwin_ser.write(senddata)

                    temp_list = list(senddata.hex())
                    log_message = []
                    for i in range (0, len(temp_list), 2):
                        log_message.append(temp_list[i] + temp_list[i+1])
                    logpool.append('>>>>>  %a' % log_message)
                    senddata = None
    
   


    def msginterpret(self, x):      #Dwin
        if len(x) > 6:
            value = []
            variable = x[4] + x[5]                         # variabila de pe bytes 4 si 5
            for i in range(7, 7 + 2*int(x[6])):                      # se itereaza toti bytes pana la final
                if x[i] != 'ff':
                    value.append(x[i])
            return variable, value

        elif x == ['5a', 'a5', '03', '82', '4f', '4b']:
            # print("<<<<< confirmare")
            return '0000', ['4f' ,'4b']

        else: 
            # print('!!!!! ERONAT !!!!!')
            return '0000', ['ff', 'ff']



    def page_switch(self, page):        #Dwin
        global dwin_tobesent, current_page

        current_page = page
        
        finaldata = (b'\x5A\xA5\x07\x82\x00\x84\x5A\x01\x00'+
                    (bytes(chr(int(page)), 'utf-8'))
        )
        # print('\npage switch %s' % page)
        dwin_tobesent.append(finaldata)


    def display_results(self, coin1ban, coin5bani, coin10bani, coin50bani):
        global dwin_tobesent, total
        
        try:
            total = int(coin1ban*1 + coin5bani*5 + coin10bani*10 + coin50bani*50)
            # print('total %i' % total)
        except ValueError as error:
            print (error)

        finaldata = (
            b'\x5a\xa5\x0f\x82\x20\x00' +                       # scriere valori in Vp 2000
            coin1ban.to_bytes(2, byteorder = 'big') + 
            coin5bani.to_bytes(2, byteorder = 'big') +
            coin10bani.to_bytes(2, byteorder = 'big') +
            coin50bani.to_bytes(2, byteorder = 'big') + 
            total.to_bytes(4, byteorder = 'big'))
        dwin_tobesent.append(finaldata)

        # print(finaldata)    



    def display_collection(self, transdb):
        global dwin_tobesent

        try:
            db = sqlite3.connect(transdb)

            cursor = db.cursor()

            sqlite_select_query = '''SELECT * 
                    FROM    Storage
                    WHERE   tr_id = (SELECT MAX(tr_id)  FROM Storage)'''
            
            cursor.execute(sqlite_select_query)

            records = cursor.fetchall()

            # sqlite_insert_with_param = """INSERT INTO 'Storage'
            #                     ('coin01', 'coint05', 'coin10', 'coin50', 'total', 'timestart', 'timeend') 
            #                     VALUES (?, ?, ?, ?, ?, ?, ?);"""

            if records:
                for row in records:
                    last01 = row[1]
                    last05 = row[2]
                    last10 = row[3]
                    last50 = row[4]
                    lasttotal = row[5]

                    
            else:
                last01 = 0
                last05 = 0
                last10 = 0
                last50 = 0
                lasttotal = 0

        except Exception as e:
            print("eroare citire ultimul update pe colectare", e)

        print(last01, last05, last10, last50, lasttotal)

        finaldata = (
            b'\x5a\xa5\x0f\x82\x20\x10' +                       # scriere valori in Vp 2010
            last01.to_bytes(2, byteorder = 'big') + 
            last05.to_bytes(2, byteorder = 'big') +
            last10.to_bytes(2, byteorder = 'big') +
            last50.to_bytes(2, byteorder = 'big') + 
            int(lasttotal*100).to_bytes(4, byteorder = 'big'))
        logpool.append('***')
        dwin_tobesent.append(finaldata)
        logpool.append('***')








class sql:

    def initialization (transdb, table):
        try:
            db = sqlite3.connect('transactions.db')

            cursor = db.cursor()

            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS %s
                        (tr_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                        coin01  INT,
                        coint05  INT,
                        coin10   INT,
                        coin50   INT,
                        total    FLOAT,
                        timestart TIMESTAMP,
                        timeend TIMESTAMP);
                        ''' % table)
                print("a fost creata tabela", table)
            except Exception as e:
                print("S-a bulit", e)
            
            cursor.close()

        except Exception as e:
            print ("Nu i-a convenit asta", e)
        finally:
            if db:
                db.close()




    
    def ins_transaction (coin01, coin05, coin10, coin50, total, starttime, endtime, transdb):
        try:
            db = sqlite3.connect(transdb)

            cursor = db.cursor()

            sqlite_insert_with_param = """INSERT INTO 'Transactions'
                                ('coin01', 'coint05', 'coin10', 'coin50', 'total', 'timestart', 'timeend') 
                                VALUES (?, ?, ?, ?, ?, ?, ?);"""

            data_tuple = (coin01, coin05, coin10, coin50, total/100, starttime, endtime)

            cursor.execute(sqlite_insert_with_param, data_tuple)

            db.commit()

            # aflam care e numarul ultimei tranzactii din db
            sqlite_select_query = '''SELECT * 
                    FROM    Storage
                    WHERE   tr_id = (SELECT MAX(tr_id)  FROM Transactions)'''

            cursor.execute(sqlite_select_query)
            records = cursor.fetchall()
            if records:
                for row in records:
                    last_transaction = row[0]

            cursor.close()

            try:
                transaction_receipt(data_tuple, last_transaction)
            except Exception as e:
                print (e)


        except Exception as e:
            print("Nu a mers inserarea deoarece", e)
        finally:
            db.close()




    def add_storage (coin01, coin05, coin10, coin50, total, transdb):
        try:
            db = sqlite3.connect(transdb)

            cursor = db.cursor()

            sqlite_select_query = '''SELECT * 
                    FROM    Storage
                    WHERE   tr_id = (SELECT MAX(tr_id)  FROM Storage)'''
            
            cursor.execute(sqlite_select_query)

            records = cursor.fetchall()

            sqlite_insert_with_param = """INSERT INTO 'Storage'
                                ('coin01', 'coint05', 'coin10', 'coin50', 'total', 'timestart', 'timeend') 
                                VALUES (?, ?, ?, ?, ?, ?, ?);"""

            if records:
                for row in records:
                    last01 = row[1]
                    last05 = row[2]
                    last10 = row[3]
                    last50 = row[4]
                    lasttotal = row[5]
                    laststart = row[6]
                    

                    data_tuple = (coin01 + last01, coin05 + last05, coin10 + last10, coin50 + last50, total/100 + lasttotal, laststart, datetime.now())
            else:
                data_tuple = (coin01, coin05, coin10, coin50, total/100, datetime.now(), datetime.now())


            cursor.execute(sqlite_insert_with_param, data_tuple)

            db.commit()
            cursor.close()
        except Exception as e:
            print("Nu a mers adaugare storage deoarece", e)
        finally:
            db.close()




    def collect (transdb):
        try:
            db = sqlite3.connect(transdb)

            cursor = db.cursor()

            
            # OPERATIUNE PE TABELA STORAGE PENTRU 
            # - CITIREA ULTIMEI INREGISTRARI
            # - INTRODUCEREA LINIEI CU ZERO
            sqlite_select_query = '''SELECT * 
                    FROM    Storage
                    WHERE   tr_id = (SELECT MAX(tr_id)  FROM Storage)'''
            
            cursor.execute(sqlite_select_query)

            records = cursor.fetchall()


            if records:
                for row in records:
                    last01 = row[1]
                    last05 = row[2]
                    last10 = row[3]
                    last50 = row[4]
                    lasttotal = row[5]
                    laststart = datetime.strptime(row[6], '%Y-%m-%d %H:%M:%S.%f')
                    collection = (last01, last05, last10, last50, lasttotal, laststart, datetime.now())
                    # collection = datetime.now()

            else:
                collection = (0, 0, 0, 0, 0, datetime.now(), datetime.now())

            sqlite_insert_with_param = """INSERT INTO 'Storage'
                                ('coin01', 'coint05', 'coin10', 'coin50', 'total', 'timestart', 'timeend') 
                                VALUES (?, ?, ?, ?, ?, ?, ?);"""

            data_tuple = (0, 0, 0, 0, 0, datetime.now(), datetime.now())

      

            cursor.execute(sqlite_insert_with_param, data_tuple)


            # OPERATIUNI PE TABELA COLLECTION PENTRU INREGISTRAREA REZULTATELOR COLECTARII
            sqlite_insert_with_param = """INSERT INTO 'Collection'
                                ('coin01', 'coint05', 'coin10', 'coin50', 'total', 'timestart', 'timeend') 
                                VALUES (?, ?, ?, ?, ?, ?, ?);"""
            
            cursor.execute(sqlite_insert_with_param, collection)

            db.commit()



            # aflam care e numarul ultimei colectari (chiar cea in curs) din db
            sqlite_select_query = '''SELECT * 
                    FROM    Storage
                    WHERE   tr_id = (SELECT MAX(tr_id)  FROM Collection)'''


            cursor.execute(sqlite_select_query)
            records = cursor.fetchall()
            if records:
                for row in records:
                    last_collection = row[0]


            cursor.close()

            try:
                collection_receipt(collection, last_collection)
            except Exception as e:
                print("eroare la apelarea functie collection_receipt", e)


            print("am facut colectare")

            return collection
            
       
        except Exception as e:
            print("Nu a mers sa facem colectare deoarece", e)
        finally:
            db.close()








def principalul(lock):
    global dwin_rcvdmsg
    global ribao_rcvdmsg
    global i, timer
    global motor_check, motor_state, current_page, topage0, starttime, page02, page04, page10
    global coin1ban, coin5bani, coin10bani, coin50bani, total

    while True:
        # print("***                #")


    ##### Zona de verificare status motor
        try: 
            if motor_check == 1 and (datetime.now() - timer).microseconds > 900000:
                ribao_tobesent.append(b'\xfe\x06\xef\xad\x00\xab')
                timer = datetime.now()
        except Exception as e:
            print(e)


        try:
            if motor_check == 1 and motor_state == '00':
                motor_check = 0
        except Exception as e:
            print(e)


        try:
            if motor_state == '00':
                dwin.page_switch('0003')
                motor_state = 'ff'
        except Exception as e:
            print(e)

    ##### END


    ##### Zona de temporizare inainte de a muta pe pagina zero
    
        # print(timer.second)
        
        try:
            if topage0 == 1 and (datetime.now() - timer).seconds > 3:
                print((datetime.now() - timer).seconds)
                dwin.page_switch(0000)
                topage0 = 0
        except Exception as e:
            print(e)
    ##### END




    ##### Zona Switch to page02
        try:
            if page02 == True:
                starttime = datetime.now()                              # marcam timpul de incepere tranzactie

                dwin.page_switch('0002')
                ribao_tobesent.append(b'\xfe\x06\xef\xa3\x00\xa5')      # dam comanda start count

                motor_check = 1    
                page02 = False
        except Exception as e:
            print("Exception la page02", e)
    ##### END


    ##### Zona Switch to page04
        try:
            if page04 == True:
                dwin.page_switch('0004')

                try:
                    # Scriem tranzactia in tabela de tranzactii
                    sql.ins_transaction(coin1ban, coin5bani, coin10bani, coin50bani, total, starttime, datetime.now(), "transactions.db")
                    
                    print(coin1ban, coin5bani, coin10bani, coin50bani, total, starttime, datetime.now())

                    # Scriem update in tabela de monede colectate
                    sql.add_storage (coin1ban, coin5bani, coin10bani, coin50bani, total, "transactions.db")

                    coin1ban = 0
                    coin5bani = 0
                    coin10bani = 0
                    coin50bani = 0
                    total = 0
                except Exception as e:
                    print("nu a mers sa facem inserarea", e)
                
                
                try:
                    # reinitializare numarare masina si display
                    ribao_tobesent.append(b'\xfe\x06\xef\xa5\x00\xa3')
                    dwin.display_results(0, 0, 0, 0)
                except ValueError as error:
                    logpool.append(f'eroare {error}')

                timer = datetime.now()

                topage0 = 1

                page04 = False
        except Exception as e:
            print("Exception la page04", e)
    ##### END




    ##### Zona Switch to page10
        try:
            if page10 == True:
                dwin.page_switch('0010')
                print('sunte la pagina 10')

                inputID = -1
                inputPIN = -1


                while inputID == -1 or inputPIN ==-1:
                    temp = ''

                    print("%i   %i" % (inputID, inputPIN))

                    while len(dwin_rcvdmsg) == 0:
                        pass

                    x = dwin_rcvdmsg.pop(0)
                    print (x)

                    for i in range(0, 2*int(x[6],16)):
                        if x[7+i] != 'ff':
                            temp += codecs.decode(x[7+i], 'hex').decode("ASCII")
                    if (x[4] + x[5]) == '1100':
                        inputID = int(temp)
                        print("inputID = %i" % inputID)
                    if (x[4] + x[5]) == '1104':
                        inputPIN = int(temp)
                        print("inputPIN = %i" % inputPIN)

                
                print('avem si ID si PIN, facem return')
                if inputID == userID and inputPIN == userPIN:
                    try:
                        dwin.display_collection("transactions.db")
                    except Exception as e:
                        print(e)
                    dwin.page_switch(12)
                else:
                    dwin.page_switch(14)

                # resetare valori pentru a nu ramane afisate pe ecran la uramtoarea tura
                dwin_tobesent.append (b'\x5a\xa5\x0f\x82\x11\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff')

                page10 = False
        except Exception as e:
            print("Exception la page10", e)
    ##### END    






        with lock:

            if len(dwin_rcvdmsg):
                x = dwin_rcvdmsg.pop(0)
                res = dwin.msginterpret(x)


                match res[0]:
                    case '1000':
                        page = int(res[1][0] + res[1][1])
                        # print('page %i' % page)

                        match page:
                            case 2:
                                page02 = True

                            case 4:
                                page04 = True

                            case 10:
                                page10 = True

                            case 12:
                                try:
                                    dwin.display_collection("transactions.db")
                                except Exception as e:
                                    print(e)
                                dwin.page_switch(page)

                            case 15:
                                try:
                                    collection = sql.collect("transactions.db")
                                    for i in collection:
                                        print (i)
                                except Exception as e:
                                    print (e)

                                try:
                                    dwin.page_switch(15)
                                except Exception as e:
                                    print (e)

                            case _:
                                dwin.page_switch(page)

            
                    case _:
                        pass


            if len(ribao_rcvdmsg):
                ribao_msg = ribao_rcvdmsg.pop(0)
                ribao.msginterpret(ribao_msg)

      




if __name__ == "__main__":
    
    # global coin1ban, coin5bani, coin10bani, coin50bani, total


    # coin1ban = 0
    # coin5bani = 0
    # coin10bani = 0
    # coin50bani = 0
    # total = 0

    log_path = './logger.log'
    try:
        file_max(log_path, 2000 * 1024)
    except:
        pass
    logging.basicConfig(level=logging.WARNING,

                        format='%(asctime)s - %(message)s',

                        datefmt='%Y-%m-%d %H:%M:%S', filename=log_path)



  
    sql.initialization("transactions.db", "Transactions")
    sql.initialization("transactions.db", "Storage")
    sql.initialization("transactions.db", "Collection")
    
    
    i = 21
    

    logpool = []

    ribao_tobesent = []
    ribao_rcvdmsg = []

    dwin_tobesent = []
    dwin_rcvdmsg = []

    ribao_ser = serial.Serial(ribao_port, baudrate)  # open serial port for Ribao module
    dwin_ser = serial.Serial(dwin_port, baudrate)  # open serial port for DWIN display

    ribao = Ribao()
    dwin = Dwin()

    # initiem 3 treaduri pe langa cel principal
    # dwin.com_listener - monitorizare mesaje venite de la dwin
    # dwin.send_msg - trimitere mesaje catre dwin
    # logger - tread general de logare
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=6) 
    m = multiprocessing.Manager()
    lock = m.Lock()

    a = executor.submit(ribao.com_listener, ribao_ser, lock)   
    b = executor.submit(ribao.send_msg, ribao_ser, lock)
    c = executor.submit(dwin.com_listener, dwin_ser, lock)
    d = executor.submit(dwin.send_msg, dwin_ser, lock)
    e = executor.submit(logger, lock)
    f = executor.submit(principalul, lock)
    # g = executor.submit(wait, lock)


    logpool.append ("$$$ THE MAIN CODE HAS STARTED $$$")

  
    # reinitializare numarare masina si display
    ribao_tobesent.append(b'\xfe\x06\xef\xa5\x00\xa3')
    dwin.display_results(0, 0, 0, 0)
    dwin.page_switch(0)

    
  


