import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { HomeComponent } from './home.component';
import { DetailAgencyComponent } from './detail-agency.component';

const routes: Routes = [
  { path: 'home', component: HomeComponent },
  { path: 'detail/:id', component: DetailAgencyComponent },
  { path: 'detail', redirectTo: '/home', pathMatch: 'full' },
  { path: '', redirectTo: '/home', pathMatch: 'full' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
