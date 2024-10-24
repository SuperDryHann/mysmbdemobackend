
class Development(BaseModel):
    planning_pathway: str = Field( 
        description="Pathway of planning, e.g., 'Complying Development' or Local Council",
    )
    development_type: str = Field(
        ...,
        description="Type of development that a user quries",
    )
    zone: str = Field(
        ...,
        description="",
    )
    zone_description: str = Field(
        ...,
        description="",
    )
    minimum_lot_size: str = Field(
        ...,
        description="",
    )
    minimum_lot_width: str = Field(
        ...,
        description="",
    )
    minimum_front_setback: str = Field(
        ...,
        description="",
    )
    minimum_side_setback: str = Field(
        ...,
        description="",
    )
    minimum_real_setback: str = Field(
        ...,
        description="",
    )
    maximum_percentage_of_lot_used: str = Field(
        ...,
        description="",
    )
    maximum_area: str = Field(
        ...,
        description="",
    )
    maximum_building_height: str = Field(
        ...,
        description="",
    )
    additional_criteria: str = Field(
        ...,
        description="",
    )



class DevelopmentCategory(BaseModel):
    """Choose all categories that user input satisfy."""
    category: str = Field(
        ...,
        description='Category that satisfy user input'
    )
    developmentType: str = Field(
        ...,
        description='"Development Type" field THE Category'
    )
    planningPathway: str = Field(
        ...,
        description='"Planning Pathway" field the Category'
    )
    zone: str = Field(
        ...,
        description='"Zone" field THE Category'
    )
    lotSize: str = Field(
        ...,
        description='"Minimum Lot Size (sqm)" field THE Category'
    )
    lotWidth: str = Field(
        ...,
        description='Development Type field THE Category'
    )
    frontSetback: str = Field(
        ...,
        description='Development Type field THE Category'
    )
    sideSetback: str = Field(
        ...,
        description='Development Type field THE Category'
    )
    rearSetback: str = Field(
        ...,
        description='Development Type field THE Category'
    )
    percentageOfLotUsed: str = Field(
        ...,
        description='Development Type field THE Category'
    )
    area: str = Field(
        ...,
        description='Development Type field THE Category'
    )
    buildingHeight: str = Field(
        ...,
        description='Development Type field THE Category'
    )










