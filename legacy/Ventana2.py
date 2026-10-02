import tkinter as tk
from PyAudio import*
import threading

def ventana2():
	ventana = tk.Tk()  # Genero Ventana
	ventana.title("Digital Rider SPA")
	ventana.geometry("500x500") #You want the size of the app to be 500x500
	ventana.resizable(0, 0)
	GrabarAudioSimple = tk.Button(ventana, text='Grabar Audio', command=Audio1Canal)
	GrabarAudioSimple.grid(row=0,column=0)

	GrabarAudioPorCanal = tk.Button(ventana, text='Grabar dependiendo de un umbral', command=Recorderfunction())
	GrabarAudioPorCanal.grid(row=0,column=1)
	ventana.mainloop()
def Recorderfunction():
	threading.Thread(target=listen).start()
