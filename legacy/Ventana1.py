from Ventana2 import ventana2
import tkinter as tk
import os
import secrets
import sqlite3
from tkinter import messagebox
UsuarioPorDefecto="Admin"
# Sin contraseña fija en el código: se toma del entorno o se genera una.
passwordPorDefecto=os.environ.get("RADIO_ADMIN_PASSWORD") or secrets.token_urlsafe(9)
if not os.environ.get("RADIO_ADMIN_PASSWORD"):
    print("Contraseña inicial de Admin:", passwordPorDefecto)
def generarVentana():
    def compararConDataBase(user,password):
        conexion=sqlite3.connect("db.sqlite3")
        consulta = conexion.cursor()
        sql =''' SELECT * FROM tablaUsuarios WHERE usuario= ? AND password= ? '''
        if (consulta.execute(sql,(user,password))):
            rows = consulta.fetchall()
            if len(rows)==0:
                messagebox.showinfo(message="Acceso denegado, datos incorrectos", title="Error de acceso")
            else:
                ventana2()

        consulta.close()#terminamos la consulta
        conexion.commit()#guardamos en la base de datos
        conexion.close()

    def cargarImagen():
        base_folder = os.path.dirname(__file__)
        image_path = os.path.join(base_folder, 'Asset\logo.png')
        photo = tk.PhotoImage(file=image_path)
        panel = tk.Label(ventana, image=photo)
        panel.pack(side="bottom", fill="both", expand="yes")

    def conectar_a_base_de_datos():
        conexion=sqlite3.connect("db.sqlite3")
        consulta = conexion.cursor()
        sql ='''
        CREATE TABLE IF NOT EXISTS tablaUsuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        usuario VARCHAR(50) NOT NULL,
        password VARCHAR(50)NOT NULL)
        '''
        sqlCrearDatosPrincipales='''
        INSERT INTO tablaUsuarios(usuario,password) 
        SELECT ?, ? 
        WHERE NOT EXISTS(SELECT 1 FROM tablaUsuarios WHERE usuario =?  AND password = ?);
        '''
        if (consulta.execute(sql)):
            consulta.execute(sqlCrearDatosPrincipales,(UsuarioPorDefecto,passwordPorDefecto,UsuarioPorDefecto,passwordPorDefecto))
        else:
            print ("Surgió un error")
        consulta.close()#terminamos la consulta
        conexion.commit()#guardamos en la base de datos
        conexion.close()


    def Verificar():
        PasswordString = password.get()  # get password from entrys
        UserString=e1.get()
        compararConDataBase(UserString,PasswordString)


    ventana=tk.Tk()#Genero Ventana
    #cargarImagen()
    conectar_a_base_de_datos()
    tk.Label(ventana, text="Nombre Usuario").grid(row=0)#Etiqueta de Nombre de usuario
    e1 = tk.Entry(ventana)

    e1.grid(row=0, column=1)

    tk.Label(ventana, text="Password").grid(row=1)
    e2 = tk.Entry(ventana)
    password = tk.StringVar() #Password variable
    passEntry = tk.Entry(ventana, textvariable=password, show='*')
    passEntry.grid(row=1, column=1)
    submit = tk.Button(ventana, text='Ingresar', command=Verificar)
    submit.grid(row=2,column=1)
    ventana.title("Proyecto PyAudio")
    ventana.resizable(0, 0)
    ventana.mainloop()


if __name__ == '__main__':
    generarVentana()