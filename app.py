import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, ttk,Scale,DoubleVar
import cv2
import pytesseract
from PIL import Image, ImageTk
from datetime import datetime, timedelta
import re
import subprocess
import platform
import pandas as pd
import customtkinter
from customtkinter import CTkButton
import vlc
import os

# Configure pytesseract based on the operating system
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = os.path.join(os.path.dirname(__file__), "Tesseract-OCR", "tesseract.exe")
    print(f"tesseract path -------> {pytesseract.pytesseract.tesseract_cmd}")  
else:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def extract_timestamp(frame, x=0, y=0, w=850, h=50):
    try:
        timestamp_crop = frame[y:y+h, x:x+w]
        timestamp_grey = cv2.cvtColor(timestamp_crop, cv2.COLOR_BGR2GRAY)
        _, timestamp_thresh = cv2.threshold(timestamp_grey, 127, 255, cv2.THRESH_BINARY)
        candidate_str = pytesseract.image_to_string(timestamp_thresh, config='--psm 6')
        
        regex_str = r'Date:\s(\d{4}-\d{2}-\d{2})\sTime:\s(\d{2}:\d{2}:\d{2}\s(?:AM|PM))\sFrame:\s(\d{2}:\d{2}:\d{2}:\d{2})'
        match = re.search(regex_str, candidate_str)
        
        if match:
            date_str, time_str, frame_str = match.groups()
            return date_str, time_str, frame_str
    except Exception as e:
        print(f"Error extracting timestamp: {e}")
    return None, None, None

def get_video_timestamp(video_path, frame_position):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return extract_timestamp(frame)
    return None, None, None

def get_initial_time(video_path):
    date_str, time_str, _ = get_video_timestamp(video_path, 0)
    return time_str if time_str else "00:00:00 AM"

def get_video_end_time(video_path):
    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    date_str, time_str, _ = get_video_timestamp(video_path, frame_count - 1)
    cap.release()
    return time_str if time_str else "00:00:00 AM"

def parse_time(time_str):
    try:
        return datetime.strptime(time_str, '%I:%M:%S %p')
    except ValueError:
        pass
    
    try:
        return datetime.strptime(time_str, '%H:%M:%S')
    except ValueError:
        return None

def time_to_seconds(time_str):
    dt = parse_time(time_str)
    if dt:
        return dt.hour * 3600 + dt.minute * 60 + dt.second
    return 0

def seconds_to_time(seconds):
    return str(timedelta(seconds=seconds))

def encode_video(input_path, output_path):
    try:
        ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg-v1", "bin", "ffmpeg.exe")
        print(f"path to ffmpeg ------> {ffmpeg_path}")
        command = [
            ffmpeg_path,
            '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-crf', '18',  # Adjust quality
            '-preset', 'ultrafast',
            '-c:a', 'aac',
            '-b:a', '192k',
            output_path
        ]
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", "Failed to encode video with ffmpeg.")

def trim_video(file_path, start_time, end_time, initial_time_str):
    # Convert times to seconds
    start_time_sec = time_to_seconds(start_time)
    end_time_sec = time_to_seconds(end_time)
    
    # Convert initial_time_str to seconds
    initial_time_sec = time_to_seconds(initial_time_str)
    
    # Adjust start and end times based on the initial time extracted from OCR
    start_time_sec -= initial_time_sec
    end_time_sec -= initial_time_sec
    
    # Ensure valid times
    if start_time_sec >= end_time_sec:
        messagebox.showerror("Time Error", "Start time must be before end time.")
        return None

    # Define the output file path
    trimmed_file = file_path.replace('.mp4', '_trimmed.mp4')
    print("Trimmed video path: " + trimmed_file)

    # Create a temporary file to store trimmed video
    ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg-v1", "bin", "ffmpeg.exe")
    trim_command = [
        ffmpeg_path,
        '-y',
        '-i', file_path,
        '-ss', str(start_time_sec),
        '-to', str(end_time_sec),
        '-c:v', 'libx264',
        '-crf', '18',  # Adjust quality
        '-preset', 'ultrafast',
        '-c:a', 'aac',
        '-strict', 'experimental',
        trimmed_file
    ]
    try:
        subprocess.run(trim_command, check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", "Failed to trim video.")
        return None

    return trimmed_file


class VideoPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Player")

        # Initialize instance variables
        self.file_path = None
        self.encoded_file_path = "encoded_video.mp4"
        self.capture = None
        self.update_frame_id = None
        self.jump_time_input = "00:00:00"
        self.previous_display = None
        self.excel_data = None
        self.video_duration_seconds = 0
        self.initial_time_str = None
        self.end_time_str = None
        self.appearance_mode="System"

        # Setup GUI elements
        self.setup_gui()

    def setup_gui(self):
        # Frame for left side controls
        
        self.left_container=tk.Frame(self.root,bg="grey",highlightbackground="black",highlightthickness=1)
        self.left_container.grid(row=0,column=0,sticky="nsew")
       
       

        self.right_container=tk.Frame(self.root,bg="white",highlightbackground="black",highlightthickness=1)
        self.right_container.grid(row=0,column=1,sticky="nsew")
        self.right_container.grid_rowconfigure(0,weight=0)
        # self.right_container.grid_rowconfigure(1,weight=1)
        # self.right_container.grid_rowconfigure(2,weight=3)
        self.right_container.columnconfigure(0,weight=2)

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=15)

        # left_first container
        self.left_first_container=tk.Frame(self.left_container,bg="grey")
        self.left_first_container.grid(row=0,column=0)
        self.left_first_container.columnconfigure(0,weight=1)
        self.left_first_container.columnconfigure(1,weight=1)

        # left second container
        self.left_second_container=tk.Frame(self.left_container,bg="grey")
        self.left_second_container.grid(row=1,column=0)

        # left third container
        self.left_third_container=tk.Frame(self.left_container,bg="grey")
        self.left_third_container.grid(row=3,column=0)
        self.left_third_container.rowconfigure(0,weight=1)
        self.left_container.columnconfigure(0,weight=1)
        self.left_third_container.rowconfigure(1,weight=1)
       


        
        # video_player_container
        self.vid_player_frame=tk.Frame(self.right_container)
        self.vid_player_frame.configure(highlightbackground="black",highlightthickness=1)
        self.vid_player_frame.grid(row=0,column=0,sticky="nsew")
        self.vid_player_frame.columnconfigure(0,weight=2)

        # detail container 
        self.detail_frame=tk.Frame(self.right_container,bg="white")
        self.detail_frame.grid(row=1,column=0,sticky="nsew")
        self.detail_frame.columnconfigure(0,weight=1)
        self.detail_frame.columnconfigure(1,weight=1)
        self.detail_frame.columnconfigure(2,weight=1)
        self.detail_frame.columnconfigure(3,weight=1)
        self.detail_frame.columnconfigure(4,weight=1)
        self.detail_frame.columnconfigure(5,weight=1)

        #third_frame
        self.third_frame=tk.Frame(self.right_container,bg="white")
        self.third_frame.grid(row=2,column=0)
        self.third_frame.columnconfigure(0,weight=2)


        
        # Frame for video player
        self.video_frame = tk.Frame(self.vid_player_frame,width=640,height=480)
        self.video_frame.grid(row=0, column=0, sticky="nsew")

        # position of video playing
        self.video_label = tk.Label(self.vid_player_frame)
        self.video_label.grid(row=0, column=0, padx=5, pady=5)
        


        # Frame for search results
        self.results_frame = tk.Frame(self.third_frame)
        self.results_frame.grid(row=0, column=0, sticky="nsew")

        # Setup GUI elements on the left side
        self.label = tk.Label(self.left_first_container, text="Upload a video file to extract timestamp.",bg="grey")
        self.label.grid(row=0, column=0, columnspan=2, pady=10)

        self.upload_video_button = customtkinter.CTkButton(self.left_first_container, text="Upload Video", width=9, command=self.load_video, fg_color="green", hover_color="green")
        self.upload_video_button.grid(row=1, column=0, sticky="ew",padx=10)

        self.upload_excel_button = customtkinter.CTkButton(self.left_first_container, text="Upload File ", width=9, command=self.upload_file, fg_color="green", hover_color="green")
        self.upload_excel_button.grid(row=1, column=1, sticky="ew",padx=10)

        # Setup Excel input widgets
        self.column_entry = tk.Entry(self.left_second_container)   
        self.column_entry.grid(row=0, column=0, pady=5,padx=10)
        self.column_entry.insert(0, "Enter Fields :")  # Example default value
        self.column_entry.config(fg='gray')  # Set the text color to gray
        self.column_listbox = tk.Listbox(self.left_second_container)
        self.column_listbox.grid(row=1, column=0, pady=5,padx=10)
        self.column_listbox.bind("<<ListboxSelect>>", self.select_column)

        # self.value_label = tk.Label(self.left_container, text="Enter value:",bg="grey")
        # self.value_label.grid(row=5, column=0, pady=5)
        self.value_entry = tk.Entry(self.left_second_container)
        self.value_entry.grid(row=2, column=0, pady=5,padx=10)
        self.value_entry.insert(0, "Enter value :")  # Example default value
        self.value_entry.config(fg='gray')  # Set the text color to gray
        self.value_listbox = tk.Listbox(self.left_second_container)
        self.value_listbox.grid(row=3, column=0, pady=5,padx=10)
        self.value_listbox.bind("<<ListboxSelect>>", self.select_value)


        self.date_time_text = tk.Text(self.left_container, height=10, width=50)
        self.search_button = customtkinter.CTkButton(self.left_second_container, text="Search",font=("Helvetica", 13, "bold"), command=self.search_value, fg_color="#4681f4", hover_color="#4681f4")
        self.search_button.grid(row=4, column=0, columnspan=2, pady=4)

        self.column_entry.bind("<KeyRelease>", self.update_column_suggestions)
        self.value_entry.bind("<KeyRelease>", self.update_value_suggestions)
        self.column_entry.bind('<FocusIn>',self.on_entry_click)
        self.column_entry.bind('<FocusOut>',self. on_focusout) 
        self.value_entry.bind('<FocusIn>',self.on_entry_click_val)
        self.value_entry.bind('<FocusOut>',self. on_focusout_val) 

        # Setup video player frame
        self.initial_time_label = tk.Label(self.detail_frame, text="Initial Time :", font=("Helvetica", 12),bg="white")
        self.initial_time_label.grid(row=0, column=0, pady=5)

        self.end_time_label = tk.Label(self.detail_frame, text="End Time :", font=("Helvetica", 12),bg="white")
        self.end_time_label.grid(row=0, column=5, pady=5)

        self.jump_time_entry = tk.Entry(self.detail_frame, width=20,highlightbackground="black",highlightthickness=1)
        self.jump_time_entry.grid(row=4, column=1, pady=5,)
        self.jump_time_entry.insert(0, "00:00:00")  # Example default value

        self.jump_button = customtkinter.CTkButton(self.detail_frame, text="Jump to Time", command=self.jump_to_time, state=tk.DISABLED, fg_color="green", hover_color="green")
        self.jump_button.grid(row=4, column=3, pady=5)

        self.skip_backward_button = customtkinter.CTkButton(self.detail_frame, text="Skip -5 sec", command=self.skip_backward, fg_color="#008080", hover_color="#008080")
        self.skip_backward_button.grid(row=0, column=1, pady=10)
        
        self.skip_forward_button = customtkinter.CTkButton(self.detail_frame, text="Skip +5 sec", command=self.skip_forward, fg_color="#008080", hover_color="#008080")
        self.skip_forward_button.grid(row=0, column=3, pady=10)



        self.progress_value = tk.IntVar(master=self.vid_player_frame)
        self.progress_slider = tk.Scale(self.vid_player_frame, variable=self.progress_value, from_=0, to=0, orient="horizontal", command=self.seek)
        self.progress_slider.grid(row=1, column=0, columnspan=2, padx=5, sticky="ew")
        self.progress_slider.configure(state="disabled")
        
    

        self.results_frame.grid_rowconfigure(0, weight=1)
        self.results_frame.grid_rowconfigure(1, weight=0)
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.results_frame.grid_columnconfigure(1, weight=0)

        # trim elements
        self.start_label = tk.Label(self.left_third_container, text="Trim",bg="grey")
        self.start_label.grid(row=0,column=0)

        self.dummy1_label = tk.Label(self.left_third_container,bg="grey")
        self.dummy1_label.grid(row=1,column=0)

        self.start_entry = tk.Entry(self.left_third_container)
        self.start_entry.grid(row=2,column=0)
        self.start_entry.insert(0,"Start Time :")
        self.start_entry.config(fg='gray') 

        self.dummy2_label = tk.Label(self.left_third_container,bg="grey")
        self.dummy2_label.grid(row=4,column=0)

        self.end_entry = tk.Entry(self.left_third_container)
        self.end_entry.grid(row=5,column=0)

        self.end_entry.insert(0,"End Time :")
        self.end_entry.config(fg='gray') 

        self.start_entry.bind('<FocusIn>',self.on_trim_click)
        self.start_entry.bind('<FocusOut>',self. on_trim) 
        self.end_entry.bind('<FocusIn>',self.on_trim_click_val)
        self.end_entry.bind('<FocusOut>',self. on_trim_val) 
        

        self.dummy3_label = tk.Label(self.left_third_container,bg="grey")
        self.dummy3_label.grid(row=6,column=0)

        self.trim_button = customtkinter.CTkButton(self.left_third_container, text="Trim and Download Video", command=self.trim_and_download,fg_color="#008080")
        self.trim_button.grid(row=7,column=0)

        self.capture = None
        self.update_frame_id = None
        self.file_path = None
        self.encoded_file_path = None


    def on_entry_click(self,event):
        # """function that gets called whenever entry is clicked"""
        if self.column_entry.cget('fg') == 'gray':
            self.column_entry.delete(0, "end")  # delete all the text in the entry
            self.column_entry.insert(0, '')  # Insert blank for user input
            self.column_entry.config(fg='black')  # Set the text color to black

    def on_focusout(self,event):
        if self.column_entry.get() == '':
            self.column_entry.insert(0, "Enter Fields :")
            self.column_entry.config(fg='gray')

    def on_entry_click_val(self,event):
        # """function that gets called whenever entry is clicked"""
        if self.value_entry.cget('fg') == 'gray':
            self.value_entry.delete(0, "end")  # delete all the text in the entry
            self.value_entry.insert(0, '')  # Insert blank for user input
            self.value_entry.config(fg='black')  # Set the text color to black

    def on_focusout_val(self,event):
        if self.value_entry.get() == '':
            self.value_entry.insert(0, "Enter value :")
            self.value_entry.config(fg='gray')

    # for trim entry        
    def on_trim_click(self,event):
        # """function that gets called whenever entry is clicked"""
        if self.start_entry.cget('fg') == 'gray':
            self.start_entry.delete(0, "end")  # delete all the text in the entry
            self.start_entry.insert(0, '')  # Insert blank for user input
            self.start_entry.config(fg='black')  # Set the text color to black

    def on_trim(self,event):
        if self.start_entry.get() == '':
            self.start_entry.insert(0, "Start Time :")
            self.start_entry.config(fg='gray')

    def on_trim_click_val(self,event):
        # """function that gets called whenever entry is clicked"""
        if self.end_entry.cget('fg') == 'gray':
            self.end_entry.delete(0, "end")  # delete all the text in the entry
            self.end_entry.insert(0, '')  # Insert blank for user input
            self.end_entry.config(fg='black')  # Set the text color to black

    def on_trim_val(self,event):
        if self.end_entry.get() == '':
            self.end_entry.insert(0, "End Time :")
            self.end_entry.config(fg='gray')

      


    def load_video(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov")])
        
        if self.file_path:
            self.encoded_file_path = self.file_path.replace('.mp4', '_encoded.mp4')
            encode_video(self.file_path, self.encoded_file_path)

            # self.vlc_instance = vlc.Instance()
            # self.player = self.vlc_instance.media_player_new()
            # self.player.set_mrl(self.file_path)
            # self.player.set_hwnd(self.video_label.winfo_id())
            
            # self.player.play()

            self.capture = cv2.VideoCapture(self.encoded_file_path)
            if not self.capture.isOpened():
                messagebox.showerror("Error", "Could not open video.")
                return

            self.extract_times()
        else:
            messagebox.showerror("Error", "No video uploaded.")

    def upload_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx; *.xls")])
        if not file_path:
            return

        try:
            if file_path.endswith('.xlsx'):
                self.excel_data = pd.read_excel(file_path, engine='openpyxl')
            elif file_path.endswith('.xls'):
                self.excel_data = pd.read_excel(file_path, engine='xlrd')
            else:
                raise ValueError("Unsupported file format. Please select a valid Excel file.")

            self.column_suggestions = list(self.excel_data.columns)
            self.value_suggestions = {
                col: self.excel_data[col].dropna().unique().tolist() for col in self.excel_data.columns
            }

            # Clear existing listbox items
            self.column_listbox.delete(0, tk.END)
            self.value_listbox.delete(0, tk.END)
            self.date_time_text.delete(1.0, tk.END)  # Clear text widget

            # Inform user that the file was uploaded successfully
            messagebox.showinfo("Success", "Excel file uploaded successfully. Start typing to get column suggestions.")
            
        except ValueError as ve:
            messagebox.showerror("Error", f"Failed to process the file: {ve}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read the Excel file: {str(e)}")




    def update_column_suggestions(self, event):
        search_text = self.column_entry.get().lower()
        self.column_listbox.delete(0, tk.END)
        
        if search_text:
            suggestions = [col for col in self.column_suggestions if search_text in col.lower()]
            for suggestion in suggestions:
                self.column_listbox.insert(tk.END, suggestion)



    def select_column(self, event):
        selection = self.column_listbox.curselection()
        if selection:
            column_name = self.column_listbox.get(selection[0])
            self.column_entry.delete(0, tk.END)
            self.column_entry.insert(0, column_name)
            self.update_value_suggestions(None)  # Update value suggestions based on selected column

    def update_value_suggestions(self, event):
        search_text = self.value_entry.get().lower()
        self.value_listbox.delete(0, tk.END)
        
        selected_column = self.column_entry.get()
        if selected_column and selected_column in self.value_suggestions:
            values = self.value_suggestions[selected_column]
            if search_text:
                suggestions = [val for val in values if search_text in str(val).lower()]
                for suggestion in suggestions:
                    self.value_listbox.insert(tk.END, suggestion)

    def select_value(self, event):
        selection = self.value_listbox.curselection()
        if selection:
            value = self.value_listbox.get(selection[0])
            self.value_entry.delete(0, tk.END)
            self.value_entry.insert(0, value)
                # self.display_date_time()  # Display corresponding DATE AND TIME values
    def search_value(self):
            column_name = self.column_entry.get()
            value = self.value_entry.get()

            if column_name in self.excel_data.columns:
                filtered_df = self.excel_data[self.excel_data[column_name] == value]

                # Create Treeview widget only when search button is clicked
                self.tree = ttk.Treeview(self.results_frame, columns=("QR CODE", "Name", "Company Name", "Phone", "Email", "DATE AND TIME"), show='headings')
                self.tree.heading("QR CODE", text="QR CODE")
                self.tree.heading("Name", text="Name")
                self.tree.heading("Company Name", text="Company Name")
                self.tree.heading("Phone", text="Phone")
                self.tree.heading("Email", text="Email")
                self.tree.heading("DATE AND TIME", text="DATE AND TIME")

                self.v_scroll = ttk.Scrollbar(self.results_frame, orient=tk.VERTICAL, command=self.tree.yview)
                # self.h_scroll = ttk.Scrollbar(self.results_frame, orient=tk.HORIZONTAL, command=self.tree.xview)

                self.tree.grid(row=0, column=0, sticky="nsew",)
                self.v_scroll.grid(row=0, column=1, sticky="ns")
                # self.h_scroll.grid(row=1, column=0, sticky="ew")
                self.tree.configure(yscrollcommand=self.v_scroll.set)
                # self.tree.selection("I001")

                self.tree.column("QR CODE", width=170)
                self.tree.column("Name", width=170)
                self.tree.column("Company Name", width=150)
                self.tree.column("Phone", width=170)
                self.tree.column("Email", width=170)
                self.tree.column("DATE AND TIME", width=170)

                style = ttk.Style()
                style.configure('Treeview', rowheight=14,highlightbackground="black",highlightthickness=2)
                style.configure("Treeview.Heading", font=("Arial", 8, "bold"))
                style.configure("Treeview", font=("Arial", 9,"bold"))

                self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

                # Insert new rows
                for index, row in filtered_df.iterrows():
                    self.tree.insert("", tk.END, values=list(row))

                if filtered_df.empty:
                    messagebox.showinfo("No Results", "No matching results found.")
            else:
                messagebox.showerror("Error", "Column name not found in the Excel file.")

    def display_date_time(self):
        column_name = self.column_entry.get()
        value = self.value_entry.get()
        
        if column_name in self.excel_data.columns:
            filtered_df = self.excel_data[self.excel_data[column_name] == value]
            date_times = filtered_df["DATE AND TIME"].tolist()
            
            # Update text widget with DATE AND TIME values
            self.date_time_text.delete(1.0, tk.END)
            if date_times:
                for date_time in date_times:
                    self.date_time_text.insert(tk.END, str(date_time) + "\n")
            else:
                self.date_time_text.insert(tk.END, "No matching DATE AND TIME values found.")

    def extract_times(self):
        if self.file_path:
            self.initial_time_str = get_initial_time(self.encoded_file_path)
            self.end_time_str = get_video_end_time(self.encoded_file_path)
            
            self.initial_time_label.configure(text=f"Initial Time: {self.initial_time_str}")
            self.end_time_label.configure(text=f"End Time: {self.end_time_str}")

            self.jump_button.configure(state=tk.NORMAL)
            self.start_entry.delete(0, 'end')
            self.start_entry.insert(0, "00:00:00")
            self.end_entry.delete(0, 'end')
            self.end_entry.insert(0, "00:00:00")
            
            self.set_slider_range()
            self.play_video()

    def set_slider_range(self):
        if self.capture:
            total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.video_duration_seconds = total_frames / self.capture.get(cv2.CAP_PROP_FPS)
            self.progress_slider.configure(to=self.video_duration_seconds)
            self.progress_slider.configure(state="normal")

    def play_video(self):
        if self.update_frame_id is not None:
            self.root.after_cancel(self.update_frame_id)
        
        self.update_frame()

    def update_frame(self):
        if self.capture:
            success, frame = self.capture.read()
            if success:
                frame_width = 720
                frame_height = int((frame.shape[0] / frame.shape[1]) * frame_width)
                resized_frame = cv2.resize(frame, (frame_width, frame_height))
                img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))
                self.tk_img = ImageTk.PhotoImage(img)
                self.video_label.configure(image=self.tk_img)

                current_frame = self.capture.get(cv2.CAP_PROP_POS_FRAMES)
                current_time = current_frame / self.capture.get(cv2.CAP_PROP_FPS)
                self.progress_value.set(current_time)

                self.update_frame_id = self.root.after(30, self.update_frame)
            else:
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.update_frame_id = self.root.after(30, self.update_frame)

    def jump_to_time(self):
        jump_time_str = self.jump_time_entry.get()
        jump_seconds = time_to_seconds(jump_time_str)
        initial_seconds = time_to_seconds(self.initial_time_str)
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            messagebox.showerror("Error", "Failed to get video frame rate.")
            return
        
        target_seconds = jump_seconds - initial_seconds
        total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration_seconds = total_frames / fps
        
        if target_seconds < 0:
            target_seconds = 0
        elif target_seconds > total_duration_seconds:
            target_seconds = total_duration_seconds
        
        frame_position = int(target_seconds * fps)
        
        if frame_position >= total_frames:
            frame_position = total_frames - 1
        elif frame_position < 0:
            frame_position = 0
        
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
        self.play_video()

    def skip_forward(self):
        self.skip(5)

    def skip_backward(self):
        self.skip(-5)

    def skip(self, seconds):
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        current_position = self.capture.get(cv2.CAP_PROP_POS_FRAMES)
        total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_offset = seconds * fps
        
        new_position = int(current_position + frame_offset)
        if new_position < 0:
            new_position = 0
        elif new_position >= total_frames:
            new_position = total_frames - 1
        
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, new_position)
        self.play_video()

    def seek(self, value):
        if self.capture:
            fps = self.capture.get(cv2.CAP_PROP_FPS)
            frame_position = int(float(value) * fps)
            total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if frame_position < 0:
                frame_position = 0
            elif frame_position >= total_frames:
                frame_position = total_frames - 1
            
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
            self.play_video()

    def on_row_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            selected_values = self.tree.item(selected_item, 'values')
            if len(selected_values) >= 6:
                date_time_str = selected_values[5]
                jump_seconds = time_to_seconds(date_time_str)
                self.jump_to_time_from_seconds(jump_seconds)

    def jump_to_time_from_seconds(self, jump_seconds):
        initial_seconds = time_to_seconds(self.initial_time_str)
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            messagebox.showerror("Error", "Failed to get video frame rate.")
            return
        
        target_seconds = jump_seconds - initial_seconds
        total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration_seconds = total_frames / fps
        
        if target_seconds < 0:
            target_seconds = 0
        elif target_seconds > total_duration_seconds:
            target_seconds = total_duration_seconds
        
        frame_position = int(target_seconds * fps)
        
        if frame_position >= total_frames:
            frame_position = total_frames - 1
        elif frame_position < 0:
            frame_position = 0
        
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
        self.play_video()

    def trim_and_download(self):
        if not self.file_path:
            messagebox.showerror("Error", "No video loaded.")
            return

        start_time = self.start_entry.get()
        end_time = self.end_entry.get()

        if not start_time or not end_time:
            messagebox.showerror("Error", "Please enter both start and end times.")
            return

        if not self.initial_time_str:
            messagebox.showerror("Error", "Initial time is not available.")
            return

        trimmed_file = trim_video(self.encoded_file_path, start_time, end_time, self.initial_time_str)
        if trimmed_file:
            messagebox.showinfo("Success", f"Video trimmed successfully and saved to {trimmed_file}")


# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.mainloop()
