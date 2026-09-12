from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class CountEvent:

    event_uuid: str
    branch_id: int
    camera_name: str
    track_id: int
    event_type: str
    occurred_at: str
    synchronized: int = 0

    @classmethod
    def create(
        cls,
        branch_id: int,
        camera_name: str,
        track_id: int,
        event_type: str
    ):

        event_type = event_type.upper()

        if event_type not in ("IN", "OUT"):
            raise ValueError(
                "event_type debe ser IN u OUT"
            )

        return cls(
            event_uuid=str(uuid4()),
            branch_id=branch_id,
            camera_name=camera_name,
            track_id=track_id,
            event_type=event_type,
            occurred_at=(
                datetime.now()
                .astimezone()
                .isoformat(
                    timespec="seconds"
                )
            ),
            synchronized=0
        )