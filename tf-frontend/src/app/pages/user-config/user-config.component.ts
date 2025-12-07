import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClientModule } from '@angular/common/http';
import { AuthService, CandidatoRequest, EmpresaRequest } from '../../services/auth.service';

@Component({
  selector: 'app-user-config',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './user-config.component.html',
  styleUrls: ['./user-config.component.css']
})
export class UserConfigComponent {
  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

  // Selector de tipo de usuario
  userType: 'candidato' | 'empresa' = 'candidato';

  // Datos comunes
  commonData = {
    email: '',
    password: '',
    confirmPassword: '',
    nombre: ''
  };

  // Datos específicos de candidatos
  candidatoData = {
    apellido: '',
    gender: '',
    birthDate: ''
  };

  // Datos específicos de empresas
  empresaData = {
    descripcion: ''
  };

  // Estados de validación
  birthDateError = false;
  loading = false;
  errorMessage = '';
  profilePicture: File | null = null;

  // Cambiar tipo de usuario
  onUserTypeChange(type: 'candidato' | 'empresa'): void {
    this.userType = type;
    // Limpiar datos específicos al cambiar
    this.candidatoData = {
      apellido: '',
      gender: '',
      birthDate: ''
    };
    this.empresaData = {
      descripcion: ''
    };
    this.birthDateError = false;
  }

  // Validación de email
  isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  // Validación de contraseñas coincidentes
  passwordsMatch(): boolean {
    if (!this.commonData.password || !this.commonData.confirmPassword) {
      return true;
    }
    return this.commonData.password === this.commonData.confirmPassword;
  }

  // Validaciones específicas de candidatos
  preventInvalidChars(event: KeyboardEvent): void {
    const allowed = /^[a-zA-ZÁÉÍÓÚÑáéíóúñ\s]$/;
    if (!allowed.test(event.key)) {
      event.preventDefault();
    }
  }

  sanitizeName(field: 'apellido'): void {
    const input = this.candidatoData[field];
    this.candidatoData[field] = input.replace(/[^a-zA-ZÁÉÍÓÚÑáéíóúñ\s]/g, '');
  }

  hasInvalidChars(value: string): boolean {
    return /[^a-zA-ZÁÉÍÓÚÑáéíóúñ\s]/.test(value);
  }

  checkAge(): void {
    if (!this.candidatoData.birthDate) {
      this.birthDateError = false;
      return;
    }

    const birth = new Date(this.candidatoData.birthDate);
    const today = new Date();
    const age = today.getFullYear() - birth.getFullYear();
    const m = today.getMonth() - birth.getMonth();
    this.birthDateError = age < 18 || (age === 18 && m < 0);
  }

  // ACTUALIZADO: Validación de CV con IA
  // Método para foto de perfil (opcional)
  onProfilePictureSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    
    if (file && file.type.startsWith('image/')) {
      this.profilePicture = file;
      console.log('📷 Foto de perfil seleccionada:', file.name);
    } else if (file) {
      alert('La foto de perfil debe ser una imagen válida.');
      this.profilePicture = null;
    }
  }

  // Validar formulario según el tipo (simplificado)
  isFormValid(): boolean {
    const commonValid = this.commonData.email &&
                       this.commonData.password &&
                       this.commonData.confirmPassword &&
                       this.commonData.nombre &&
                       this.isValidEmail(this.commonData.email) &&
                       this.passwordsMatch();

    if (this.userType === 'candidato') {
      return !!(commonValid &&
             this.candidatoData.apellido &&
             this.candidatoData.gender &&
             this.candidatoData.birthDate &&
             !this.birthDateError &&
             !this.hasInvalidChars(this.candidatoData.apellido));
    } else {
      return !!(commonValid && this.empresaData.descripcion);
    }
  }

  onSubmit(): void {
    if (!this.isFormValid()) {
      return;
    }

    this.loading = true;
    this.errorMessage = '';

    if (this.userType === 'candidato') {
      this.registerCandidato();
    } else {
      this.registerEmpresa();
    }
  }

  // Registro de candidato (simplificado - sin verificación)
  private registerCandidato(): void {
    const candidatoData: CandidatoRequest = {
      email: this.commonData.email,
      password: this.commonData.password,
      nombre: this.commonData.nombre,
      apellido: this.candidatoData.apellido,
      genero: this.candidatoData.gender as 'masculino' | 'femenino' | 'otro',
      fecha_nacimiento: this.candidatoData.birthDate
    };

    console.log('🚀 Registrando candidato...');

    this.authService.registerCandidato(candidatoData, this.profilePicture || undefined).subscribe({
      next: (response: any) => {
        console.log('✅ Registro exitoso:', response);

        alert('¡Registro exitoso! Ya puedes iniciar sesión.');

        // Navegar al login directamente
        this.router.navigate(['/login']);
      },
      error: (error: any) => {
        this.handleError(error);
      },
      complete: () => {
        this.loading = false;
      }
    });
  }

  // Navegar de vuelta al login
  goBackToLogin(): void {
    this.router.navigate(['/login']);
  }

  // Registro de empresa (simplificado - sin verificación)
  private registerEmpresa(): void {
    const empresaData: EmpresaRequest = {
      email: this.commonData.email,
      password: this.commonData.password,
      nombre: this.commonData.nombre,
      descripcion: this.empresaData.descripcion
    };

    this.authService.registerEmpresa(empresaData, this.profilePicture || undefined).subscribe({
      next: (response: any) => {
        console.log('✅ Empresa registrada exitosamente:', response);

        alert('¡Empresa registrada exitosamente! Ya puedes iniciar sesión.');

        // Navegar al login directamente
        this.router.navigate(['/login']);
      },
      error: (error: any) => {
        this.handleError(error);
      },
      complete: () => {
        this.loading = false;
      }
    });
  }

  private handleError(error: any): void {
    console.error('Error al registrar:', error);
    this.loading = false;

    if (error.error && error.error.detail) {
      this.errorMessage = error.error.detail;
    } else if (error.status === 400) {
      this.errorMessage = 'El email ya está registrado o hay datos inválidos.';
    } else if (error.status === 0) {
      this.errorMessage = 'No se pudo conectar con el servidor. Verifica que la API esté ejecutándose.';
    } else {
      this.errorMessage = 'Error inesperado. Por favor, intenta nuevamente.';
    }
  }
}