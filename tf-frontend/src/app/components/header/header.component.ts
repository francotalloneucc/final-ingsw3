import { Component, OnInit } from '@angular/core';
import { Router, NavigationEnd, RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [RouterModule, CommonModule],
  templateUrl: './header.component.html',
  styleUrl: './header.component.css'
})
export class HeaderComponent implements OnInit {

  isLandingPage: boolean = false;
  isMyUserPage: boolean = false;
  isAdminDashboardPage: boolean = false;
  isLoggedIn: boolean = false;
  currentUser: any = null;
  isAdmin: boolean = false;

  constructor(
    private router: Router,
    private authService: AuthService,
    private userService: UserService
  ) {}

  ngOnInit() {
    // Escuchar cambios de autenticación
    this.authService.isLoggedIn$.subscribe(loggedIn => {
      this.isLoggedIn = loggedIn;
      if (loggedIn) {
        this.loadUserData();
      } else {
        this.currentUser = null;
        this.isAdmin = false;
      }
    });

    // Validar token al iniciar
    this.authService.validateToken().subscribe(isValid => {
      this.isLoggedIn = isValid;
      if (isValid) {
        this.loadUserData();
      }
    });

    // Escuchar cambios de ruta
    this.router.events.subscribe(event => {
      if (event instanceof NavigationEnd) {
        this.checkCurrentRoute(event.url);
      }
    });

    // Verificar estado inicial
    this.checkCurrentRoute(this.router.url);
  }

  checkCurrentRoute(url: string) {
    // Limpiar query params
    const cleanUrl = url.split('?')[0];

    // Detectar páginas
    const landingRoutes = ['/', '/home', '/landing'];
    this.isLandingPage = landingRoutes.includes(cleanUrl);
    this.isMyUserPage = cleanUrl.includes('/my-user') || cleanUrl.includes('/mi-perfil');
    this.isAdminDashboardPage = cleanUrl.includes('/admin-dashboard');
  }

  async loadUserData() {
    try {
      this.currentUser = await this.userService.getCurrentUser().toPromise();
      this.isAdmin = this.currentUser?.role === 'admin';
    } catch (error) {
      console.error('Error cargando datos del usuario:', error);
      this.isAdmin = false;
    }
  }

  // Métodos de navegación
  onLogin() { this.router.navigate(['/login']); }
  onRegister() { this.router.navigate(['/register']); }
  onLogout() { this.authService.logout(); }
  onProfile() { this.router.navigate(['/mi-perfil']); }
  onAdminDashboard() { this.router.navigate(['/admin-dashboard']); }
}
