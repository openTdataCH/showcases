import { Component, OnInit } from '@angular/core';

import { DataService } from './data.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
  public isDataLoaded = false;
  public loadingMessage = 'Loading business organisations...';

  constructor(private dataService: DataService) {}

  async ngOnInit(): Promise<void> {
    try {
      const csv = await this.dataService.fetchBusinessOrganisationsCSV();
      await this.dataService.businessOrganisationsController.loadFromCSV(csv);
      this.isDataLoaded = true;
    } catch (error) {
      this.loadingMessage = 'Could not load business organisations. Please reload the page to try again.';
      console.error(error);
    }
  }
}
