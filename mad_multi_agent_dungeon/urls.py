from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('send_command_api/', views.send_command_api, name='send_command_api'),
    path('agent/<str:agent_name>/', views.agent_detail_view, name='agent_detail'),
    path('api/agent/<str:agent_name>/', views.agent_detail_api, name='agent_detail_api'),
    path('api/agent/<str:agent_name>/start/', views.start_agent, name='start_agent'),
    path('api/agent/<str:agent_name>/stop/', views.stop_agent, name='stop_agent'),
    path('api/agent/<str:agent_name>/reset/', views.reset_agent, name='reset_agent'),
    path('api/agent/<str:agent_name>/update_prompt/', views.update_prompt, name='update_prompt'),
]
