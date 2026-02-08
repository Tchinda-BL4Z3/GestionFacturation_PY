from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

def home(request):
    return render(request, 'facturation/homePage.html')

def login_selection(request):
    return render(request, 'facturation/LogIn.html')

def login_admin(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Vérification des identifiants définis
        if email == "admin@gmail.com" and password == "admin1234":
            return redirect('/admin/') 
        else:
            error = "Identifiants administrateur incorrects."

    return render(request, 'facturation/login_admin.html', {'error': error})

def login_caissier(request):
    error = None
    if request.method == "POST":
        emp_id = request.POST.get('employee-id')
        pin = request.POST.get('pin-code')

        # Test simple des identifiants caissier
        if emp_id == "EMP-001" and pin == "1234":
            
            return redirect('home') 
        else:
            error = "Identifiant ou Code PIN incorrect."

    return render(request, 'facturation/login_caissier.html', {'error': error})

def register_client(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')

        if password != confirm_password:
            error = "Les mots de passe ne correspondent pas."
        else:
            return redirect('login') 

    return render(request, 'facturation/register_client.html', {'error': error})

def login_client(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        if email == "client@gmail.com" and password == "client1234":
            return redirect('home') 
        else:
            error = "Identifiants client incorrects."

    return render(request, 'facturation/login_client.html', {'error': error})