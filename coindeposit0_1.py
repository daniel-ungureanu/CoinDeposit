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



# la apelarea acestei functii, daca s-a atins dimensiunea maxima a fisierului, 
# se sterg primele 1000 de randuri (cele mai vechi)
def file_max(fname, max):
    if os.path.getsize(fname) > max:
        subprocess.call('sed -i \'1,1000d\' ' + fname, shell=True)



def logger(lock):
    global logpool
    
    while True:
        time.sleep(0.01)
        with lock: 
            if len(logpool):
                logging.warning(logpool.pop(0))
           





class Ribao:                                 
    def com_listener(self, ribao_ser, lock):      # Ribao
        global ribao_rcvdmsg
        global logpool

       
        
        while True:
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
            time.sleep(0.01)
            with lock:
                if len(ribao_tobesent):
                    senddata = ribao_tobesent.pop(0)
                    ribao_ser.write(senddata)

                    temp_list = list(senddata.hex())
                    log_message = []
                    for i in range (0, len(temp_list), 2):
                        log_message.append(temp_list[i] + temp_list[i+1])
                    logpool.append('>#>#>  %a' % log_message)
                    senddata = None
                    
  

    def msginterpret(self, x):      # Ribao
        global coin1ban, coin5bani, coin10bani, coin50bani
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
                    pass
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
        global dwin_tobesent
        
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
            b'\x5a\xa5\x0f\x82\x20\x00' + 
            coin1ban.to_bytes(2, byteorder = 'big') + 
            coin5bani.to_bytes(2, byteorder = 'big') +
            coin10bani.to_bytes(2, byteorder = 'big') +
            coin50bani.to_bytes(2, byteorder = 'big') + 
            total.to_bytes(4, byteorder = 'big'))
        dwin_tobesent.append(finaldata)

        # print(finaldata)    


    def page02(self):           # Dwin
        global starttime

        starttime = datetime.now()

        # dwin.page_switch('0002')
        ribao_tobesent.append(b'\xfe\x06\xef\xa3\x00\xa5')
        # print(f'incercam ribao.running - {ribao.running}')
        # print('cucu')
        dwin.page_switch('0003')
        # print ("########## incepem while ##############")
        # while ribao.running == 0:
        #     pass
        # print ("########## am iesit din while ##############")



    def page04(self):
        global coin1ban, coin5bani, coin10bani, coin50bani, total, starttime
        try:
            sql.ins_transaction(coin1ban, coin5bani, coin10bani, coin50bani, total, starttime, datetime.now(), "transactions.db")
            
            print(coin1ban, coin5bani, coin10bani, coin50bani, total, starttime, datetime.now())

            sql.add_collection (coin1ban, coin5bani, coin10bani, coin50bani, total, "transactions.db")

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
            dwin.page_switch('0004')
        except ValueError as error:
            logpool.append(f'eroare {error}')



    def page10(self):           # Dwin
        global userID, userPIN

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
            dwin.page_switch(12)
        else:
            dwin.page_switch(14)

        # resetare valori pentru a nu ramane afisate pe ecran la uramtoarea tura
        dwin_tobesent.append (b'\x5a\xa5\x0f\x82\x11\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff')




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
                print("a fost creata tabela")
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
            cursor.close()
        except Exception as e:
            print("Nu a mers inserarea deoarece", e)
        finally:
            db.close()


    def add_collection (coin01, coin05, coin10, coin50, total, transdb):
        try:
            db = sqlite3.connect(transdb)

            cursor = db.cursor()

            sqlite_select_query = '''SELECT * 
                    FROM    Collection
                    WHERE   tr_id = (SELECT MAX(tr_id)  FROM Collection)'''
            
            cursor.execute(sqlite_select_query)

            records = cursor.fetchall()

            sqlite_insert_with_param = """INSERT INTO 'Collection'
                                ('coin01', 'coint05', 'coin10', 'coin50', 'total', 'timestart', 'timeend') 
                                VALUES (?, ?, ?, ?, ?, ?, ?);"""

            if records:
                for row in records:
                    last01 = row[1]
                    last05 = row[2]
                    last10 = row[3]
                    last50 = row[4]
                    lasttotal = row[5]

                    data_tuple = (coin01 + last01, coin05 + last05, coin10 + last10, coin50 + last50, total/100 + lasttotal, datetime.now(), datetime.now())
            else:
                data_tuple = (coin01, coin05, coin10, coin50, total/100, datetime.now(), datetime.now())

    

            cursor.execute(sqlite_insert_with_param, data_tuple)

            db.commit()
            cursor.close()
        except Exception as e:
            print("Nu a mers adaugare colectare deoarece", e)
        finally:
            db.close()

def principalul(lock):
    global dwin_rcvdmsg
    global ribao_rcvdmsg

    while True:
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
                                dwin.page02()

                            case 4:
                                dwin.page04()


                            case 10:
                                dwin.page10()

                            case _:
                                dwin.page_switch(page)

            
                    case _:
                        pass


            if len(ribao_rcvdmsg):
                ribao_msg = ribao_rcvdmsg.pop(0)
                ribao.msginterpret(ribao_msg)

      




if __name__ == "__main__":
    


    log_path = './logger.log'
    try:
        file_max(log_path, 2000 * 1024)
    except:
        pass
    logging.basicConfig(level=logging.WARNING,

                        format='%(asctime)s - %(message)s',

                        datefmt='%Y-%m-%d %H:%M:%S', filename=log_path)



  
    sql.initialization("transactions.db", "Transactions")
    sql.initialization("transactions.db", "Collection")
    
   
    

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


    logpool.append ("$$$ THE MAIN CODE HAS STARTED $$$")

  
    # reinitializare numarare masina si display
    ribao_tobesent.append(b'\xfe\x06\xef\xa5\x00\xa3')
    dwin.display_results(0, 0, 0, 0)
    dwin.page_switch(0)

    # while True:
    #     if a.running() == False:
    #         logpool.append ('************* Thread ERROR: Ribao com listener is out')
    #         # print ('Ribao com listener is out')

    #     if b.running() == False:
    #         logpool.append ('************* Thread ERROR: Ribao com sender is out')
    #         # print ('Ribao com sender is out')

    #     if c.running() == False:
    #         logpool.append ('************* Thread ERROR: dwin com listener is out')
    #         # print ('dwin com listener is out')


    #     if d.running() == False:
    #         logpool.append ('************* Thread ERROR: dwin com sender is out')
    #         # print ('dwin com sender is out')


    #     if e.running() == False:
    #         logpool.append ('************* Thread ERROR: logger is out')
    #         # print ('logger is out')

    
    #     if f.running() == False:
    #         logpool.append ('************* Thread ERROR: Main is out')
    #         print ('************* Main is out')


  


