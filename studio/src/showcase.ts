// The layouts "Look at it" opens with in Simple mode. Each is a layout the calibration measured against the game (tests/fixtures/render/*/fixture.json names them; tests/test_showcase.py pins that
// every name here is one of them), so the picture a beginner sees first is one the render is known to draw reasonably. The labels are plain words for the game's own layout names.
export interface Showcase { name: string; label: string; what: string }

export const SHOWCASE: Showcase[] = [
  { name: 'LoansTile_4x2', label: 'Loans tile', what: 'A card from the squad screen' },
  { name: 'SquadAtmosphereTile_4x2', label: 'Atmosphere tile', what: 'A card from the squad screen' },
  { name: 'MedicalCentreTile_4x2', label: 'Medical centre tile', what: 'A card from the squad screen' },
  { name: 'TacticsTile_4x4', label: 'Tactics tile', what: 'A larger card' },
  { name: 'TrainingTile_4x4', label: 'Training tile', what: 'A larger card' },
  { name: 'PreferencesFMMenuCard', label: 'Preferences card', what: 'The menu card of the Preferences screen' },
]
