--------------------------------------------------------
--  DDL for Table TBLPLAYERS
--------------------------------------------------------

  CREATE TABLE "NETFL"."TBLPLAYERS" 
   (	"OID" NUMBER(10,0), 
	"LASTNAME" VARCHAR2(50 BYTE), 
	"FIRSTNAME" VARCHAR2(50 BYTE), 
	"REALTEAMID" NUMBER(2,0), 
	"TEAMID" NUMBER(4,0), 
	"ISONINJUREDRESERVE" NUMBER(1,0) DEFAULT 0, 
	"WEEKOFFPUP" NUMBER(2,0), 
	"STARTER" VARCHAR2(5 BYTE), 
	"POSITIONID" NUMBER(4,0), 
	"INJURYSTATUS" VARCHAR2(1 BYTE), 
	"JERSEYNUMBER" NUMBER(2,0), 
	"NFLURL" VARCHAR2(100 BYTE), 
	"PRACTICESTATUS" VARCHAR2(40 BYTE), 
	"INJURY" VARCHAR2(40 BYTE), 
	"CBSID" NUMBER, 
	"GSIS" VARCHAR2(10 BYTE)
   ) SEGMENT CREATION IMMEDIATE 
  PCTFREE 10 PCTUSED 40 INITRANS 1 MAXTRANS 255 
 NOCOMPRESS LOGGING
  STORAGE(INITIAL 524288 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1
  BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "NETFL" ;
--------------------------------------------------------
--  DDL for Index IDX$$_00010001
--------------------------------------------------------

  CREATE INDEX "NETFL"."IDX$$_00010001" ON "NETFL"."TBLPLAYERS" ("LASTNAME", "FIRSTNAME") 
  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS 
  STORAGE(INITIAL 65536 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1
  BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "NETFL" ;
--------------------------------------------------------
--  DDL for Index SYS_C008705
--------------------------------------------------------

  CREATE UNIQUE INDEX "NETFL"."SYS_C008705" ON "NETFL"."TBLPLAYERS" ("OID") 
  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS 
  STORAGE(INITIAL 196608 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1
  BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "NETFL" ;
--------------------------------------------------------
--  DDL for Trigger tr_tblplayer_a_upd
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE TRIGGER "NETFL"."tr_tblplayer_a_upd" 
  after update of teamid, realteamid, positionid, firstname, lastname, weekoffpup, isoninjuredreserve 
  on TBLPLAYERS for each row
declare  

  lNewPos tblPositions.position%TYPE;
  lOldPos tblPositions.position%TYPE;
  lNewNFLTeam tblRealTeams.teamabbreviation%TYPE;
  lOldNFLTeam tblRealTeams.teamabbreviation%TYPE;
  
begin

      -- drafted = 1
      -- signed = 2
      -- cut = 3
      -- acquired (trade) = 4
      -- protected = 5
      -- info changed = 6

  -- signed/drafted
  if :old.teamid is null and :new.teamid is not null then

    if draft.get_draft_status = 0 then
         
      insert into tblplayerhistory
      ( playerid, historytypeid, actingteamid )
      values
      ( :new.oid, 2, :new.teamid );

      -- player history for drafted players has moved to draft.draft_player
      -- so that the round and pick can be recorded in the history record

    end if;

  -- cut
  elsif :old.teamid is not null and :new.teamid is null then
  
    insert into tblplayerhistory
    ( playerid, historytypeid, actingteamid )
    values
    ( :new.oid, 3, :old.teamid );
    
  -- traded
  elsif :old.teamid != :new.teamid then

    lNewPos := null;

-- moved this to the trade package so that additional information (tradeid)
-- could be saved with the history  
--    select teamabbrev into lNewTeam from tblTeams where oid = :new.teamid;
--    select teamabbrev into lOldTeam from tblTeams where oid = :old.teamid;
--  
--    insert into tblplayerhistory
--    ( playerid, historytypeid, actingteamid, narrative )
--    values
--    ( :new.oid, 4, :new.teamid, 'Traded from ' || lOldTeam || ' to ' || lNewTeam );
    
  elsif :old.teamid = :new.teamid then 

    select teamabbreviation into lNewNFLTeam from tblRealTeams where oid = :new.realteamid;
    select teamabbreviation into lOldNFLTeam from tblRealTeams where oid = :old.realteamid;
    select position into lNewPos from tblPositions where oid = :new.positionid;
    select position into lOldPos from tblPositions where oid = :old.positionid;
  
    insert into tblplayerhistory
    ( playerid, historytypeid, actingteamid, narrative )
    values
    ( :new.oid, 6, :new.teamid, 'Changed from ' || 
      :old.FirstName || ' ' || :old.LastName || ' ' || LTRIM(RTRIM(lOldPos)) || ' ' || LTRIM(RTRIM(lOldNFLTeam)) || ' PUP:' || :old.weekoffpup || ' IR:' || :old.isoninjuredreserve
      || ' to ' || 
      :new.FirstName || ' ' || :new.LastName || ' ' || LTRIM(RTRIM(lNewPos)) || ' ' || LTRIM(RTRIM(lNewNFLTeam)) || ' PUP:' || :new.weekoffpup || ' IR:' || :new.isoninjuredreserve );    

  end if;
  
end;




/
ALTER TRIGGER "NETFL"."tr_tblplayer_a_upd" ENABLE;
BEGIN 
  DBMS_DDL.SET_TRIGGER_FIRING_PROPERTY('"NETFL"','"tr_tblplayer_a_upd"',FALSE) ; 
END;

/
--------------------------------------------------------
--  DDL for Trigger tr_tblplayer_b_upd
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE TRIGGER "NETFL"."tr_tblplayer_b_upd" 
  before update of realteamid, isoninjuredreserve 
  on TBLPLAYERS for each row
declare  

begin

  -- IF a player goes on IR or has been cut in the NFL (realteamid = 32 ), 
  -- make sure the starter field gets cleared
  if :new.isoninjuredreserve = 1 and :old.isoninjuredreserve = 0 then
      :new.starter := null;
  end if;
  
  if :new.realteamid = 32 and :old.realteamid <> 32 then
      :new.starter := null;
  end if;

end;




/
ALTER TRIGGER "NETFL"."tr_tblplayer_b_upd" ENABLE;
BEGIN 
  DBMS_DDL.SET_TRIGGER_FIRING_PROPERTY('"NETFL"','"tr_tblplayer_b_upd"',FALSE) ; 
END;

/
--------------------------------------------------------
--  DDL for Trigger TR_TBLPLAYERS_B_INS
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE TRIGGER "NETFL"."TR_TBLPLAYERS_B_INS" BEFORE
INSERT ON "TBLPLAYERS" FOR EACH ROW 
begin
  if :new.oid is null then
    select SEQ_TBLPLAYERS_OID.nextval into :new.oid from dual;
  end if;
end;




/
ALTER TRIGGER "NETFL"."TR_TBLPLAYERS_B_INS" ENABLE;
--------------------------------------------------------
--  DDL for Trigger TR_TBLPLAYERS_OID
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE TRIGGER "NETFL"."TR_TBLPLAYERS_OID" 
  before
insert on TBLPLAYERS for each row
begin
  if :new.oid is null then
    select "SEQ_TBLPLAYERS_OID".nextval into :new.oid from dual;
  end if;
end;




/
ALTER TRIGGER "NETFL"."TR_TBLPLAYERS_OID" ENABLE;
--------------------------------------------------------
--  Constraints for Table TBLPLAYERS
--------------------------------------------------------

  ALTER TABLE "NETFL"."TBLPLAYERS" MODIFY ("OID" NOT NULL ENABLE);
  ALTER TABLE "NETFL"."TBLPLAYERS" MODIFY ("ISONINJUREDRESERVE" NOT NULL ENABLE);
  ALTER TABLE "NETFL"."TBLPLAYERS" MODIFY ("POSITIONID" NOT NULL ENABLE);
  ALTER TABLE "NETFL"."TBLPLAYERS" ADD PRIMARY KEY ("OID")
  USING INDEX PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS 
  STORAGE(INITIAL 196608 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1
  BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "NETFL"  ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table TBLPLAYERS
--------------------------------------------------------

  ALTER TABLE "NETFL"."TBLPLAYERS" ADD FOREIGN KEY ("TEAMID")
	  REFERENCES "NETFL"."TBLTEAMS" ("OID") ENABLE;
  ALTER TABLE "NETFL"."TBLPLAYERS" ADD FOREIGN KEY ("REALTEAMID")
	  REFERENCES "NETFL"."TBLREALTEAMS" ("OID") ENABLE;
  ALTER TABLE "NETFL"."TBLPLAYERS" ADD CONSTRAINT "TBLPLAYERS_FK51055482855351" FOREIGN KEY ("POSITIONID")
	  REFERENCES "NETFL"."TBLPOSITIONS" ("OID") ENABLE;
