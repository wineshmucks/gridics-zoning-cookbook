from __future__ import annotations
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

# --- 1. Generic & Shared Models ---

class GridicsAttribute(BaseModel):
    Id: int
    AttributeType: int
    AttributeValue: str
    Description: Optional[str] = None
    IsEnabled: Optional[bool] = None

# --- 2. Overlays & Uses ---

class GridicsOverlay(BaseModel):
    Id: int
    Name: str
    Description: Optional[str] = None
    CalibrationType: int
    GridicsId: Optional[str] = None
    Attributes: List[GridicsAttribute] = []

class GridicsUse(BaseModel):
    CalibrationUsesLabelId: int
    AllowedUsesId: int
    TypeId: int
    TypeName: str
    TypeNameLabel: Optional[str] = None
    AllowedUsesLabel: str
    AllowedUsesName: str
    AllowedUsesDescription: str
    UseConditionId: int
    CalibrationUsesLabel: str
    CalibrationUsesLabelClassId: int
    CalibrationUsesLabelClassName: str
    CalibrationUseLabelAttributes: List[GridicsAttribute] = []
    UseAllowanceAttributes: List[Any] = []
    UseLimitAttributes: List[Any] = []
    ParkingRequiredAttributes: List[Any] = []

# --- 3. Envelope & Allowances ---

class GridicsEnvelope(BaseModel):
    AreaAllowedByFloorplate: Optional[float] = None
    DensityNet: Optional[float] = None
    DensityUnits: Optional[int] = None
    FloorAreaRatio: Optional[float] = None
    FloorAreaRatioCapacity: Optional[float] = None
    LodgingCapacity: Optional[int] = None
    LotAreaAcres: Optional[float] = None
    LotAreaFeet: Optional[float] = None
    LotAreaPR: Optional[float] = None
    LotAreaFeetGAPI: Optional[float] = None
    LotCoverage: Optional[float] = None
    MaxBonusHeightAllowed: Optional[int] = None
    MaxBuildingAreaAllowed: Optional[float] = None
    MaxBuildingFootprint: Optional[float] = None
    MaxCommercialAreaAllowed: Optional[float] = None
    MaxCommercialEstablishedArea: Optional[float] = None
    MaxCommercialHeightAllowed: Optional[int] = None
    MaxLotCoverageArea: Optional[float] = None
    MaxOfficeAreaAllowed: Optional[float] = None
    MaxOfficeCommercialAllowed: Optional[float] = None
    MaxOfficeHeightAllowed: Optional[int] = None
    MaxTowersNumber: Optional[int] = None
    MinOpenSpace: Optional[float] = None
    MinOpenSpaceSquareFeet: Optional[float] = None
    PodiumArea: Optional[float] = None
    PrincipalMaxHeight: Optional[int] = None
    PrincipalMinHeight: Optional[int] = None
    PrincipalPenthouseHeight: Optional[int] = None
    PrincipalTowerHeight: Optional[int] = None
    SecondLayerDimension: Optional[float] = None
    TotalBuidingHeight: Optional[int] = None
    TowerArea: Optional[float] = None
    TowerBonusMaxHeight: Optional[int] = None
    TowerMaxArea: Optional[float] = None
    TowerMaxAreaActual: Optional[float] = None
    LodgingCapacityCalculated: Optional[int] = None
    MaximumResidentialBuildableArea: Optional[float] = None
    MaximumLodgingBuildableArea: Optional[float] = None
    
    # Setback Arrays (Often returned as single-item lists or null)
    EffectivePFrontSetbackPrincipal: Optional[List[float]] = None
    EffectivePFrontSetbackSecondary: Optional[List[float]] = None
    EffectivePRearSetback: Optional[List[float]] = None
    EffectivePSideSetback: Optional[List[float]] = None
    EffectivePWaterSetback: Optional[List[float]] = None
    EffectiveTFrontSetbackPrincipal: Optional[List[float]] = None
    EffectiveTFrontSetbackSecondary: Optional[List[float]] = None
    EffectiveTRearSetback: Optional[List[float]] = None
    EffectiveTSideSetback: Optional[List[float]] = None
    EffectiveTWaterSetback: Optional[List[float]] = None
    EffectivePeFrontSetbackPrincipal: Optional[List[float]] = None
    EffectivePeFrontSetbackSecondary: Optional[List[float]] = None
    EffectivePeRearSetback: Optional[List[float]] = None
    EffectivePeSideSetback: Optional[List[float]] = None
    
    MaxIndustrialAreaAllowed: Optional[float] = None
    MaxCivicAreaAllowed: Optional[float] = None
    MaxCivicSupportAreaAllowed: Optional[float] = None
    MaxEducationalAreaAllowed: Optional[float] = None
    TotalBuildingHeightFeet: Optional[float] = None
    
    # Gridics sometimes returns these as strings instead of floats
    EffectiveLotCoverage: Optional[str] = None
    EffectiveMinOpenSpace: Optional[str] = None
    EffectiveDensityNet: Optional[str] = None
    DensityUL: Optional[bool] = None
    LodgingDensityUL: Optional[bool] = None

class GridicsZoningAllowance(BaseModel):
    ZoneId: str
    SubZoneId: Optional[str] = None
    ZoneTypeId: Optional[str] = None
    BuildingTypologyId: Optional[str] = None
    ZoningRegulationName: str
    ZoningRegulationLink: str
    ZoneCombinationName: str

class GridicsCalibrationGeneral(BaseModel):
    PFrontSetbackPrincipalMax: Optional[float] = None
    PFrontSetbackSecondaryMax: Optional[float] = None
    PSideSetbackMax: Optional[float] = None
    PRearSetbackMax: Optional[float] = None

class GridicsFrontage(BaseModel):
    Label: str
    FrontageType: int
    Setback: float
    MinThoroughfareWidth: float
    SegmentsLengths: List[float] = []

# --- 4. Use Statistics ---

class GridicsUseTypeStat(BaseModel):
    type: int
    totalUsesCount: int
    allowed: int
    notAllowed: int

class GridicsUsesStatistic(BaseModel):
    totalUsesCount: int
    allowed: int
    notAllowed: int
    usesTypes: Dict[str, GridicsUseTypeStat]

# --- 5. Geometry & Views (Coordinates) ---

class GridicsShape(BaseModel):
    shape: List[List[float]]
    type: int

class GridicsFloorArray(BaseModel):
    start: int
    end: int
    baseHeightM: float
    heightM: float
    shapes: List[GridicsShape] = []

class GridicsZAViews(BaseModel):
    lot: Dict[str, Any] # Usually contains type: "Polygon" and coordinates
    floorsArrays: Dict[str, List[GridicsFloorArray]]
    setbacks: List[GridicsFloorArray] = []

class GridicsViews(BaseModel):
    ZA: GridicsZAViews

class GeoJSONProperties(BaseModel):
    type: str
    color: str
    height: float
    zoneсlass: str  # Note: Gridics has a cyrillic 'с' in zoneсlass in some payloads, kept as-is or mapped
    base_height: float

class GeoJSONFeature(BaseModel):
    type: str
    geometry: Dict[str, Any] # Captures Polygon/MultiPolygon coordinates dynamically
    properties: GeoJSONProperties

class GeoJSONFeatureCollection(BaseModel):
    type: str
    features: List[GeoJSONFeature]

class GridicsGeoJSONViews(BaseModel):
    CA: Optional[Any] = None
    ZA: Optional[GeoJSONFeatureCollection] = None

# --- 6. Top-Level Building & Data Models ---

class GridicsBuilding(BaseModel):
    Overlays: List[GridicsOverlay] = []
    Uses: List[GridicsUse] = []
    Envelope: GridicsEnvelope
    ZoningAllowance: GridicsZoningAllowance
    CalibrationGeneral: GridicsCalibrationGeneral
    Frontages: List[GridicsFrontage] = []
    UsesStatistic: GridicsUsesStatistic
    Views: Optional[GridicsViews] = None
    GeoJSONViews: Optional[GridicsGeoJSONViews] = None

class GridicsDataRow(BaseModel):
    Id: int
    GroupId: str
    Address: str
    State: str
    City: str
    ZipCode: str
    FolioNumber: str
    LotType: int
    CalculationStatus: int
    updatedAt: datetime
    Buildings: List[GridicsBuilding] = []

class GridicsResponse(BaseModel):
    status: str
    searchType: int
    dataRows: int
    data: List[GridicsDataRow] = []