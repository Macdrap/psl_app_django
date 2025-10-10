from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    """Main dashboard view after login"""
    return render(request, 'dashboard.html')